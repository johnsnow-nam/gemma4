"""
OCPP 1.6 / ESP32 전문 모델 파인튜닝
베이스: gemma-3-4b-it (테스트) 또는 gemma-4-9b-it (본 학습)
GPU: RTX 5070 12GB + Unsloth LoRA
"""

# ── 0. 임포트 ────────────────────────────────────────────────
from unsloth import FastLanguageModel, is_bfloat16_supported
from datasets import Dataset
from trl import SFTTrainer, TrainingArguments
import torch
import json
import os

# ── 1. 설정값 ────────────────────────────────────────────────
CONFIG = {
    # 모델 선택
    # "unsloth/gemma-3-4b-it"   → 테스트용  (빠름, 4GB VRAM)
    # "google/gemma-4-9b-it"    → 본 학습   (균형)
    # "google/gemma-4-27b-it"   → 고품질    (VRAM+RAM 필요)
    "model_name": "unsloth/gemma-3-4b-it",

    "max_seq_length": 2048,
    "load_in_4bit": True,         # VRAM 절약 (RTX 5070 12GB 기준)

    # LoRA 설정
    "lora_r": 16,                 # rank: 높을수록 품질↑ 속도↓ (8/16/32/64)
    "lora_alpha": 16,
    "lora_dropout": 0,

    # 학습 설정
    "output_dir": "./ocpp-expert-model",
    "num_train_epochs": 3,
    "per_device_train_batch_size": 2,
    "gradient_accumulation_steps": 4,  # effective batch = 2×4 = 8
    "learning_rate": 2e-4,
    "warmup_steps": 10,
    "logging_steps": 10,
    "save_steps": 50,
    "fp16": not is_bfloat16_supported(),
    "bf16": is_bfloat16_supported(),   # RTX 5070은 bf16 지원
}

# ── 2. 데이터셋 ──────────────────────────────────────────────
# 실제로는 수백~수천 개 필요. 여기선 예시 20개 포함.
# 별도 dataset.jsonl 파일이 있으면 load_from_jsonl() 사용 권장.

OCPP_DATA = [
    {
        "instruction": "BootNotification 요청 메시지의 필수 필드를 설명해줘",
        "response": """BootNotification은 충전기가 CSMS에 처음 연결될 때 보내는 메시지입니다.

필수 필드:
- chargePointModel (string): 충전기 모델명 (예: "ESP32-EVSE-01")
- chargePointVendor (string): 제조사명 (예: "MyCompany")

선택 필드:
- firmwareVersion (string): 펌웨어 버전
- chargePointSerialNumber (string): 시리얼 번호
- iccid (string): SIM 카드 번호
- imsi (string): IMSI 번호

ESP32 예시 코드:
```c
ocpp_boot_notification_t boot = {
    .chargePointVendor = "MyCompany",
    .chargePointModel  = "ESP32-EVSE-01",
    .firmwareVersion   = "1.0.0",
};
ocpp_send_boot_notification(&boot);
```

CSMS 응답으로 status (Accepted/Pending/Rejected)와 interval(heartbeat 주기)을 받습니다."""
    },
    {
        "instruction": "StartTransaction과 StopTransaction 차이를 설명하고 ESP32 코드 예시를 보여줘",
        "response": """StartTransaction: EV가 충전을 시작할 때 CSMS로 전송
StopTransaction: 충전이 종료될 때 전송

StartTransaction 필수 필드:
- connectorId: 커넥터 번호 (1부터 시작)
- idTag: RFID 카드 등 인증 토큰
- meterStart: 시작 시점 전력량 (Wh)
- timestamp: ISO 8601 형식

StopTransaction 필수 필드:
- meterStop: 종료 시점 전력량 (Wh)
- timestamp: 종료 시각
- transactionId: StartTransaction 응답에서 받은 ID

ESP32 예시:
```c
// 충전 시작
void on_ev_connected(uint8_t connector_id, const char* id_tag) {
    int32_t meter = energy_meter_read_wh();
    ocpp_start_transaction(connector_id, id_tag, meter);
}

// 충전 종료
void on_ev_disconnected(int32_t transaction_id) {
    int32_t meter = energy_meter_read_wh();
    ocpp_stop_transaction(transaction_id, meter, "EVDisconnected");
}
```"""
    },
    {
        "instruction": "MeterValues 메시지를 ESP32에서 주기적으로 보내는 방법은?",
        "response": """MeterValues는 충전 중 전력 데이터를 주기적으로 CSMS에 보고하는 메시지입니다.

전송 주기: CSMS 설정값 MeterValueSampleInterval (기본 60초)

주요 measurand 타입:
- Energy.Active.Import.Register: 누적 전력량 (Wh)
- Power.Active.Import: 현재 전력 (W)
- Current.Import: 전류 (A)
- Voltage: 전압 (V)

ESP32 FreeRTOS 태스크 예시:
```c
void meter_values_task(void *pvParam) {
    uint32_t interval_ms = 60000; // CSMS에서 받아온 값으로 교체

    while (1) {
        if (ocpp_is_transaction_active()) {
            ocpp_sampled_value_t values[] = {
                {
                    .measurand = "Energy.Active.Import.Register",
                    .value     = energy_meter_read_wh(),
                    .unit      = "Wh",
                    .context   = "Sample.Periodic",
                },
                {
                    .measurand = "Power.Active.Import",
                    .value     = power_meter_read_w(),
                    .unit      = "W",
                    .context   = "Sample.Periodic",
                },
            };
            ocpp_send_meter_values(
                g_connector_id,
                g_transaction_id,
                values,
                sizeof(values) / sizeof(values[0])
            );
        }
        vTaskDelay(pdMS_TO_TICKS(interval_ms));
    }
}
```"""
    },
    {
        "instruction": "OCPP 1.6 StatusNotification에서 ChargePointStatus 상태값을 설명해줘",
        "response": """ChargePointStatus는 커넥터 상태를 나타내는 열거형입니다.

상태 목록:
1. Available    : 충전 가능 대기 상태
2. Preparing    : EV 연결됨, 인증 대기 중
3. Charging     : 실제 충전 중 (전력 공급)
4. SuspendedEV  : EV 측에서 충전 일시정지
5. SuspendedEVSE: EVSE 측에서 충전 일시정지
6. Finishing    : 충전 완료, EV 분리 대기
7. Reserved     : 예약됨
8. Unavailable  : 사용 불가 (점검 등)
9. Faulted      : 오류 상태

IEC 61851 파일럿 신호와 매핑:
- State A (12V)  → Available
- State B (9V)   → Preparing
- State C (6V)   → Charging
- State D (3V)   → Charging (환기 필요)
- State E/F      → Faulted

ESP32 예시:
```c
void update_connector_status(cp_state_t pilot_state) {
    ocpp_status_t status;
    switch (pilot_state) {
        case CP_STATE_A: status = OCPP_STATUS_AVAILABLE;  break;
        case CP_STATE_B: status = OCPP_STATUS_PREPARING;  break;
        case CP_STATE_C: status = OCPP_STATUS_CHARGING;   break;
        case CP_STATE_E: status = OCPP_STATUS_FAULTED;    break;
        default:         status = OCPP_STATUS_UNAVAILABLE; break;
    }
    ocpp_send_status_notification(1, status, OCPP_ERROR_NO_ERROR);
}
```"""
    },
    {
        "instruction": "OCPP Heartbeat를 ESP32에서 구현하는 방법은?",
        "response": """Heartbeat는 충전기가 CSMS와 연결 유지 중임을 알리는 주기적 신호입니다.

주기: BootNotification 응답의 interval 값 (초 단위)

ESP32 FreeRTOS 구현:
```c
static uint32_t g_heartbeat_interval_s = 30; // BootNotification 응답값

void heartbeat_task(void *pvParam) {
    while (1) {
        esp_err_t ret = ocpp_send_heartbeat();
        if (ret == ESP_OK) {
            ESP_LOGI(TAG, "Heartbeat sent");
        } else {
            ESP_LOGE(TAG, "Heartbeat failed, ret=%d", ret);
            // 재연결 로직 트리거
            ocpp_reconnect();
        }
        vTaskDelay(pdMS_TO_TICKS(g_heartbeat_interval_s * 1000));
    }
}

// BootNotification 응답 콜백에서 interval 업데이트
void on_boot_notification_response(ocpp_boot_resp_t *resp) {
    if (resp->status == OCPP_BOOT_STATUS_ACCEPTED) {
        g_heartbeat_interval_s = resp->interval;
        xTaskCreate(heartbeat_task, "heartbeat", 4096, NULL, 5, NULL);
    }
}
```"""
    },
    {
        "instruction": "QCA7000S와 ESP32를 SPI로 연결해서 OCPP 메시지를 보내는 구조를 설명해줘",
        "response": """QCA7000S는 PLC(Power Line Communication) 칩으로 ISO 15118/IEC 61851 SLAC 프로토콜을 처리합니다.

하드웨어 연결 (SPI):
```
ESP32 (Master)         QCA7000S (Slave)
─────────────────────────────────────
GPIO18 (SCLK)    →    SCLK
GPIO23 (MOSI)    →    MOSI
GPIO19 (MISO)    ←    MISO
GPIO5  (CS)      →    CS
GPIO4  (INT)     ←    INT (데이터 수신 알림)
GPIO2  (RST)     →    RST
```

소프트웨어 구조:
```
EV ←── PLC 선로 ──→ QCA7000S
                        │ SPI
                       ESP32
                        │ UART/TCP
                       CSMS (OCPP)
```

ESP32 SPI 초기화:
```c
spi_device_interface_config_t qca_cfg = {
    .clock_speed_hz = 8 * 1000 * 1000, // 8MHz
    .mode           = 3,                // QCA7000S: CPOL=1, CPHA=1
    .spics_io_num   = GPIO_NUM_5,
    .queue_size     = 7,
    .pre_cb         = NULL,
};
spi_bus_add_device(HSPI_HOST, &qca_cfg, &g_qca_handle);
```

SLAC 완료 후 ISO 15118 세션 정보를 UART로 받아 OCPP StartTransaction 트리거:
```c
void on_slac_matched(slac_result_t *result) {
    // EV MAC 주소, 세션 ID 등 기록
    memcpy(g_ev_mac, result->ev_mac, 6);
    // OCPP StartTransaction 발송
    ocpp_start_transaction(1, result->ev_id_token, energy_meter_read_wh());
}
```"""
    },
    {
        "instruction": "ESP32에서 OCPP WebSocket 재연결 로직을 구현해줘",
        "response": """네트워크 끊김 시 지수 백오프(exponential backoff) 방식으로 재연결하는 것이 권장됩니다.

```c
#define RECONNECT_BASE_MS    1000   // 초기 대기 1초
#define RECONNECT_MAX_MS    30000   // 최대 대기 30초
#define RECONNECT_MULTIPLIER    2

static uint32_t g_reconnect_delay_ms = RECONNECT_BASE_MS;

void ocpp_reconnect_task(void *pvParam) {
    while (1) {
        ESP_LOGI(TAG, "OCPP 재연결 시도 (대기 %lu ms)", g_reconnect_delay_ms);
        vTaskDelay(pdMS_TO_TICKS(g_reconnect_delay_ms));

        esp_err_t ret = ocpp_websocket_connect(CONFIG_OCPP_SERVER_URL);
        if (ret == ESP_OK) {
            ESP_LOGI(TAG, "재연결 성공");
            g_reconnect_delay_ms = RECONNECT_BASE_MS; // 초기화
            ocpp_send_boot_notification();
            vTaskDelete(NULL);
        } else {
            // 지수 백오프
            g_reconnect_delay_ms = MIN(
                g_reconnect_delay_ms * RECONNECT_MULTIPLIER,
                RECONNECT_MAX_MS
            );
        }
    }
}

void on_websocket_disconnected(void) {
    ESP_LOGW(TAG, "OCPP 연결 끊김 → 재연결 태스크 시작");
    g_reconnect_delay_ms = RECONNECT_BASE_MS;
    xTaskCreate(ocpp_reconnect_task, "ocpp_reconn", 4096, NULL, 4, NULL);
}
```"""
    },
    {
        "instruction": "OCPP ChangeConfiguration 요청을 ESP32에서 처리하는 방법은?",
        "response": """ChangeConfiguration은 CSMS가 충전기 설정값을 원격으로 변경하는 메시지입니다.

처리 흐름:
1. CSMS → ESP32: ChangeConfiguration.req {key, value}
2. ESP32 검증 후 NVS에 저장
3. ESP32 → CSMS: ChangeConfiguration.conf {status}

status 값:
- Accepted: 변경 성공
- Rejected: 읽기 전용 키
- RebootRequired: 재부팅 후 적용
- NotSupported: 지원하지 않는 키

ESP32 구현:
```c
ocpp_config_status_t on_change_configuration(
    const char *key, const char *value)
{
    if (strcmp(key, "MeterValueSampleInterval") == 0) {
        int interval = atoi(value);
        if (interval < 1 || interval > 3600) {
            return OCPP_CONFIG_REJECTED;
        }
        g_meter_interval_s = interval;
        // NVS에 영구 저장
        nvs_handle_t nvs;
        nvs_open("ocpp_cfg", NVS_READWRITE, &nvs);
        nvs_set_i32(nvs, key, interval);
        nvs_commit(nvs);
        nvs_close(nvs);
        return OCPP_CONFIG_ACCEPTED;

    } else if (strcmp(key, "HeartbeatInterval") == 0) {
        g_heartbeat_interval_s = atoi(value);
        return OCPP_CONFIG_ACCEPTED;

    } else if (strcmp(key, "AuthorizationKey") == 0) {
        // 보안 키는 재부팅 필요
        strncpy(g_pending_auth_key, value, sizeof(g_pending_auth_key));
        return OCPP_CONFIG_REBOOT_REQUIRED;
    }

    return OCPP_CONFIG_NOT_SUPPORTED;
}
```"""
    },
]


def load_from_jsonl(filepath: str) -> list:
    """외부 JSONL 파일에서 데이터 로드"""
    data = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data


def format_prompt(example: dict) -> str:
    """Gemma 4 chat template 형식으로 변환"""
    return (
        "<start_of_turn>user\n"
        f"{example['instruction']}<end_of_turn>\n"
        "<start_of_turn>model\n"
        f"{example['response']}<end_of_turn>"
    )


# ── 3. 메인 학습 함수 ────────────────────────────────────────
def train():
    print("=" * 60)
    print("  OCPP / ESP32 전문 모델 파인튜닝 시작")
    print("=" * 60)

    # GPU 확인
    print(f"\n[GPU] {torch.cuda.get_device_name(0)}")
    print(f"[VRAM] {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
    print(f"[BF16] {is_bfloat16_supported()}")

    # ── 모델 로드 ──────────────────────────────────────────
    print(f"\n[1/4] 모델 로드: {CONFIG['model_name']}")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=CONFIG["model_name"],
        max_seq_length=CONFIG["max_seq_length"],
        load_in_4bit=CONFIG["load_in_4bit"],
        dtype=None,  # 자동 감지 (RTX 5070 → bf16)
    )

    # ── LoRA 설정 ──────────────────────────────────────────
    print("[2/4] LoRA 어댑터 설정")
    model = FastLanguageModel.get_peft_model(
        model,
        r=CONFIG["lora_r"],
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        lora_alpha=CONFIG["lora_alpha"],
        lora_dropout=CONFIG["lora_dropout"],
        bias="none",
        use_gradient_checkpointing="unsloth",  # VRAM 절약
        random_state=42,
    )

    # ── 데이터셋 준비 ──────────────────────────────────────
    print("[3/4] 데이터셋 준비")

    # 외부 jsonl 파일 있으면 우선 사용
    jsonl_path = "./dataset.jsonl"
    if os.path.exists(jsonl_path):
        raw_data = load_from_jsonl(jsonl_path)
        print(f"  → 외부 파일 로드: {len(raw_data)}개")
    else:
        raw_data = OCPP_DATA
        print(f"  → 내장 예시 데이터 사용: {len(raw_data)}개")
        print("  ⚠️  실제 학습은 수백~수천 개 데이터 권장")

    # 프롬프트 포맷 적용
    formatted = [{"text": format_prompt(d)} for d in raw_data]
    dataset = Dataset.from_list(formatted)
    print(f"  → 총 {len(dataset)}개 샘플")

    # ── 학습 ──────────────────────────────────────────────
    print("[4/4] 학습 시작")
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=CONFIG["max_seq_length"],
        dataset_num_proc=2,
        args=TrainingArguments(
            output_dir=CONFIG["output_dir"],
            num_train_epochs=CONFIG["num_train_epochs"],
            per_device_train_batch_size=CONFIG["per_device_train_batch_size"],
            gradient_accumulation_steps=CONFIG["gradient_accumulation_steps"],
            warmup_steps=CONFIG["warmup_steps"],
            learning_rate=CONFIG["learning_rate"],
            fp16=CONFIG["fp16"],
            bf16=CONFIG["bf16"],
            logging_steps=CONFIG["logging_steps"],
            save_steps=CONFIG["save_steps"],
            optim="adamw_8bit",       # VRAM 절약
            weight_decay=0.01,
            lr_scheduler_type="cosine",
            report_to="none",         # wandb 끄기
        ),
    )

    # 학습 전 메모리 상태
    gpu_mem = torch.cuda.memory_allocated() / 1e9
    print(f"  VRAM 사용 중: {gpu_mem:.2f} GB")

    trainer.train()

    # ── 저장 ──────────────────────────────────────────────
    print("\n[저장] LoRA 어댑터 저장 중...")
    model.save_pretrained(CONFIG["output_dir"])
    tokenizer.save_pretrained(CONFIG["output_dir"])
    print(f"  → {CONFIG['output_dir']} 저장 완료")

    # GGUF 변환 (Ollama 등록용)
    print("\n[GGUF] Q4_K_M 변환 중... (몇 분 소요)")
    model.save_pretrained_gguf(
        CONFIG["output_dir"] + "-gguf",
        tokenizer,
        quantization_method="q4_k_m",
    )
    print(f"  → {CONFIG['output_dir']}-gguf 저장 완료")

    print("\n" + "=" * 60)
    print("  학습 완료!")
    print(f"  LoRA 모델: {CONFIG['output_dir']}")
    print(f"  GGUF 모델: {CONFIG['output_dir']}-gguf")
    print("=" * 60)
    print("\n다음 단계:")
    print("  1. Modelfile 작성")
    print("  2. ollama create ocpp-expert -f Modelfile")
    print("  3. ollama run ocpp-expert")


# ── 4. 추론 테스트 함수 ──────────────────────────────────────
def test_inference():
    """학습된 모델로 간단한 추론 테스트"""
    print("\n[추론 테스트]")

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=CONFIG["output_dir"],
        max_seq_length=CONFIG["max_seq_length"],
        load_in_4bit=CONFIG["load_in_4bit"],
    )
    FastLanguageModel.for_inference(model)

    test_questions = [
        "BootNotification 응답으로 Pending을 받으면 어떻게 해야 해?",
        "ESP32에서 OCPP 메시지 큐를 어떻게 관리해야 해?",
    ]

    for q in test_questions:
        inputs = tokenizer(
            f"<start_of_turn>user\n{q}<end_of_turn>\n<start_of_turn>model\n",
            return_tensors="pt"
        ).to("cuda")

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=512,
                temperature=0.3,
                do_sample=True,
            )

        response = tokenizer.decode(outputs[0], skip_special_tokens=True)
        print(f"\nQ: {q}")
        print(f"A: {response.split('model')[-1].strip()}")
        print("-" * 40)


# ── 5. 실행 ──────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_inference()
    else:
        train()
