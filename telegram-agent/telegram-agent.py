#!/usr/bin/env python3
"""BOT-001: Telegram AI 에이전트 메인"""
from __future__ import annotations
import asyncio
import logging
import os
import tempfile

from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from agent.executor import TaskExecutor
from config.settings import TELEGRAM_BOT_TOKEN, ALLOWED_USER_ID
from tools.tool_registry import get_help_text

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ─── 전역 TaskExecutor ────────────────────────────────────────────────────────
executor = TaskExecutor()

MAX_MSG_LEN = 4096  # Telegram 메시지 최대 길이


# ─── 인증 확인 ────────────────────────────────────────────────────────────────
def _is_authorized(update: Update) -> bool:
    if not ALLOWED_USER_ID:
        return True
    return update.effective_user.id == ALLOWED_USER_ID


async def _deny(update: Update) -> None:
    await update.message.reply_text("⛔ 접근 권한이 없습니다.")


# ─── 긴 메시지 분할 전송 ──────────────────────────────────────────────────────
async def _send_long(update: Update, text: str) -> None:
    """4096자 초과 메시지를 여러 조각으로 전송"""
    if not text:
        text = "_(빈 응답)_"
    for i in range(0, len(text), MAX_MSG_LEN):
        chunk = text[i : i + MAX_MSG_LEN]
        try:
            await update.message.reply_text(
                chunk,
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            # Markdown 파싱 실패 시 plain text 로 재전송
            await update.message.reply_text(chunk)


# ─── /start ──────────────────────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        return await _deny(update)
    name = update.effective_user.first_name or "사용자"
    proj = executor.current_project_name or "없음"
    msg = (
        f"👋 안녕하세요, *{name}*님!\n\n"
        f"저는 Gemma4 기반 AI 개발 에이전트입니다.\n"
        f"현재 프로젝트: `{proj}`\n\n"
        f"/help 로 사용 가능한 명령어를 확인하세요."
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


# ─── /help ───────────────────────────────────────────────────────────────────
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        return await _deny(update)
    await update.message.reply_text(get_help_text(), parse_mode=ParseMode.MARKDOWN)


# ─── /status ─────────────────────────────────────────────────────────────────
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        return await _deny(update)
    await update.message.reply_text(
        executor.get_status_text(), parse_mode=ParseMode.MARKDOWN
    )


# ─── /projects ───────────────────────────────────────────────────────────────
async def cmd_projects(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        return await _deny(update)
    if not executor.projects:
        await update.message.reply_text("등록된 프로젝트가 없습니다.")
        return
    lines = ["*📁 등록된 프로젝트*\n"]
    for name, info in executor.projects.items():
        marker = "▶" if name == executor.current_project_name else "  "
        desc = info.get("description", "")
        path = info.get("path", "?")
        lines.append(f"{marker} `{name}`")
        if desc:
            lines.append(f"   {desc}")
        lines.append(f"   경로: `{path}`")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ─── /project <name> ─────────────────────────────────────────────────────────
async def cmd_project(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        return await _deny(update)
    if not context.args:
        proj_names = ", ".join(f"`{n}`" for n in executor.projects)
        await update.message.reply_text(
            f"사용법: `/project <이름>`\n사용 가능: {proj_names}",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    name = context.args[0]
    result = executor._switch_project(name)
    await update.message.reply_text(result, parse_mode=ParseMode.MARKDOWN)


# ─── /model [name] ───────────────────────────────────────────────────────────
async def cmd_model(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        return await _deny(update)
    if not context.args:
        await update.message.reply_text(
            f"현재 모델: `{executor.brain.model}`\n"
            f"변경하려면: `/model <모델명>`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    new_model = context.args[0]
    executor.brain.model = new_model
    await update.message.reply_text(
        f"✅ 모델 변경됨: `{new_model}`", parse_mode=ParseMode.MARKDOWN
    )


# ─── /clear ──────────────────────────────────────────────────────────────────
async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        return await _deny(update)
    executor.brain.memory.clear()
    await update.message.reply_text("🗑 대화 메모리가 초기화되었습니다.")


# ─── /save ───────────────────────────────────────────────────────────────────
async def cmd_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        return await _deny(update)
    filename = context.args[0] if context.args else None
    try:
        saved = executor.brain.memory.save(filename)
        await update.message.reply_text(
            f"💾 세션 저장됨: `{saved}`", parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ 저장 실패: {e}")


# ─── /build ──────────────────────────────────────────────────────────────────
async def cmd_build(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        return await _deny(update)
    await update.message.chat.send_action(ChatAction.TYPING)
    result = await executor._handle_build("빌드")
    await _send_long(update, result)


# ─── /diff ───────────────────────────────────────────────────────────────────
async def cmd_diff(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        return await _deny(update)
    result = await executor._handle_git("diff")
    await _send_long(update, result)


# ─── /commit ─────────────────────────────────────────────────────────────────
async def cmd_commit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        return await _deny(update)
    await update.message.chat.send_action(ChatAction.TYPING)
    result = await executor._handle_git("커밋")
    await _send_long(update, result)


# ─── /tree ───────────────────────────────────────────────────────────────────
async def cmd_tree(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        return await _deny(update)
    result = await executor._handle_structure("트리")
    await _send_long(update, result)


# ─── 일반 텍스트 메시지 ───────────────────────────────────────────────────────
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        return await _deny(update)
    user_text = update.message.text or ""
    if not user_text.strip():
        return

    await update.message.chat.send_action(ChatAction.TYPING)
    try:
        result = await executor.run(user_text)
    except Exception as e:
        logger.exception("executor.run 오류")
        result = f"⚠️ 처리 중 오류: {e}"

    await _send_long(update, result)


# ─── 이미지 메시지 ────────────────────────────────────────────────────────────
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update):
        return await _deny(update)

    await update.message.chat.send_action(ChatAction.TYPING)
    caption = update.message.caption or "이 이미지를 분석해줘"

    # 가장 큰 해상도 사진 선택
    photo = update.message.photo[-1]
    tg_file = await photo.get_file()

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        await tg_file.download_to_drive(tmp_path)
        result = executor.brain.think_with_image(caption, tmp_path)
    except Exception as e:
        logger.exception("이미지 처리 오류")
        result = f"⚠️ 이미지 분석 오류: {e}"
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    await _send_long(update, result)


# ─── 봇 명령어 메뉴 등록 ─────────────────────────────────────────────────────
async def _set_commands(app: Application) -> None:
    commands = [
        BotCommand("start",    "봇 시작"),
        BotCommand("help",     "도움말"),
        BotCommand("status",   "시스템 상태"),
        BotCommand("projects", "프로젝트 목록"),
        BotCommand("project",  "프로젝트 전환"),
        BotCommand("model",    "모델 확인/변경"),
        BotCommand("clear",    "메모리 초기화"),
        BotCommand("save",     "세션 저장"),
        BotCommand("build",    "빌드 실행"),
        BotCommand("diff",     "Git diff"),
        BotCommand("commit",   "자동 커밋"),
        BotCommand("tree",     "폴더 트리"),
    ]
    await app.bot.set_my_commands(commands)


# ─── 메인 ─────────────────────────────────────────────────────────────────────
def main() -> None:
    token = TELEGRAM_BOT_TOKEN
    if not token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN 이 설정되지 않았습니다.\n"
            ".env 파일을 확인하세요."
        )

    app = (
        Application.builder()
        .token(token)
        .build()
    )

    # 커맨드 핸들러
    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("help",     cmd_help))
    app.add_handler(CommandHandler("status",   cmd_status))
    app.add_handler(CommandHandler("projects", cmd_projects))
    app.add_handler(CommandHandler("project",  cmd_project))
    app.add_handler(CommandHandler("model",    cmd_model))
    app.add_handler(CommandHandler("clear",    cmd_clear))
    app.add_handler(CommandHandler("save",     cmd_save))
    app.add_handler(CommandHandler("build",    cmd_build))
    app.add_handler(CommandHandler("diff",     cmd_diff))
    app.add_handler(CommandHandler("commit",   cmd_commit))
    app.add_handler(CommandHandler("tree",     cmd_tree))

    # 텍스트 메시지
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # 이미지 메시지
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # 봇 커맨드 메뉴 등록 (post_init)
    app.post_init = _set_commands

    logger.info("Telegram AI 에이전트 시작")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
