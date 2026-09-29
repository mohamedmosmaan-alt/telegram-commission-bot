"""
Customer-facing conversation (§2-§8, §20), adapted for the real use case:
an agent verifies by phone, then receives their commission report.

Security requirement (explicit from the client): verification MUST use
Telegram's native "share contact" button only. Two things make this safe:
  1. The request_contact keyboard button can only ever share the phone
     number registered to the Telegram account currently using the button
     — Telegram does not let it be used to send an arbitrary number.
  2. As a second check, we also confirm `contact.user_id == sender's own
     Telegram ID`. A contact attached from someone's address book (not via
     the request_contact button) still arrives as a "contact" message, but
     its user_id will NOT match the sender unless it happens to be their
     own saved contact card — so this check rejects that path too.
There is deliberately NO manual "type your number" fallback: typing a
number proves nothing about who it belongs to.
"""
from telegram import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler

from app.bot.states import REQUEST_PHONE, AWAITING_SECONDARY_ID, WAIT_FOR_CUSTOMER_MESSAGE
from app.config.settings import settings
from app.services import customer_service
from app.services.customer_service import LookupResult
from app.services.phone import try_normalize_phone
from app.services.report_formatting import format_commission_report
from app.utils.logging_config import logger

CONTACT_KEYBOARD = ReplyKeyboardMarkup(
    [[KeyboardButton("📱 مشاركة رقم موبايلي", request_contact=True)]],
    resize_keyboard=True,
    one_time_keyboard=True,
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    telegram_user_id = update.effective_user.id

    existing = customer_service.get_session(telegram_user_id)
    if existing:
        await _send_report(update, existing)
        return WAIT_FOR_CUSTOMER_MESSAGE

    await update.message.reply_text(
        "أهلاً بيك. لعرض تقريرك، من فضلك استخدم الزرار تحت لمشاركة رقم موبايلك "
        "المسجل عندنا.\n\n"
        "⚠️ لازم تستخدم الزرار بالظبط — الأرقام المكتوبة يدويًا مش مقبولة، "
        "عشان نتأكد إن الرقم فعلاً بتاعك.",
        reply_markup=CONTACT_KEYBOARD,
    )
    return REQUEST_PHONE


async def receive_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    telegram_user_id = update.effective_user.id
    contact = update.message.contact

    # Reject any contact that isn't verifiably the sender's own number (see module docstring).
    if contact.user_id != telegram_user_id:
        await update.message.reply_text(
            "الرقم اللي اتبعت ده مش رقمك المسجل على تليجرام. من فضلك استخدم زرار "
            "\"مشاركة رقم موبايلي\" وابعت رقمك انت بس.",
            reply_markup=CONTACT_KEYBOARD,
        )
        return REQUEST_PHONE

    return await _process_phone(update, context, contact.phone_number)


async def reject_typed_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Anything typed instead of using the contact button is refused outright."""
    await update.message.reply_text(
        "من فضلك استخدم زرار \"مشاركة رقم موبايلي\" تحت — مش هينفع تكتب الرقم يدوي.",
        reply_markup=CONTACT_KEYBOARD,
    )
    return REQUEST_PHONE


async def _process_phone(update: Update, context: ContextTypes.DEFAULT_TYPE, raw_phone: str) -> int:
    telegram_user_id = update.effective_user.id
    normalized = try_normalize_phone(raw_phone, settings.default_country_code)

    if normalized is None:
        await update.message.reply_text(
            "في مشكلة في صيغة الرقم المسجل على حسابك. تواصل مع الدعم من فضلك.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    result, matches = customer_service.verify_phone(telegram_user_id, normalized)

    if result == LookupResult.NOT_FOUND:
        await update.message.reply_text(
            "الرقم ده مش مسجل عندنا كوكيل. تأكد إن الرقم المسجل على تليجرام هو نفس "
            "الرقم المسجل عندنا، أو تواصل مع الدعم.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    if result == LookupResult.DUPLICATE:
        context.user_data["pending_phone"] = normalized
        field_label = "رقم الـ Master بتاعك" if settings.duplicate_verification_field == "master" else "اسمك المسجل بالظبط"
        await update.message.reply_text(
            f"الرقم ده مسجل لأكتر من وكيل. من فضلك ابعت {field_label} لإتمام التحقق.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return AWAITING_SECONDARY_ID

    # FOUND_UNIQUE
    agent = matches[0]
    customer_service.create_session(telegram_user_id, agent)
    await _send_report(update, agent)
    return WAIT_FOR_CUSTOMER_MESSAGE


async def receive_secondary_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    telegram_user_id = update.effective_user.id
    pending_phone = context.user_data.get("pending_phone")

    if not pending_phone:
        await update.message.reply_text(
            "خلينا نبدأ من الأول. ابعت رقم موبايلك بالزرار.", reply_markup=CONTACT_KEYBOARD
        )
        return REQUEST_PHONE

    agent = customer_service.resolve_duplicate(telegram_user_id, pending_phone, update.message.text)

    if agent is None:
        await update.message.reply_text("البيانات دي مش متطابقة مع سجلاتنا لهذا الرقم. جرب تاني.")
        return AWAITING_SECONDARY_ID

    context.user_data.pop("pending_phone", None)
    customer_service.create_session(telegram_user_id, agent)
    await _send_report(update, agent)
    return WAIT_FOR_CUSTOMER_MESSAGE


async def _send_report(update: Update, agent) -> None:
    fields = customer_service.get_commission_fields(agent.master)
    if fields is None:
        await update.message.reply_text(
            f"تم التحقق من رقمك بنجاح، لكن لسه مفيش تقرير كوميشن متاح للـ Master رقم {agent.master}.\n"
            "جرّب تاني بعد شوية أو تواصل مع الدعم.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    report_text = format_commission_report(fields)
    await update.message.reply_text(
        f"✅ تم التحقق بنجاح.\n\n{report_text}",
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardRemove(),
    )


async def handle_customer_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Once verified, /start again re-sends the latest report (useful after a sync)."""
    telegram_user_id = update.effective_user.id
    session = customer_service.get_session(telegram_user_id)
    if not session:
        await update.message.reply_text(
            "الجلسة مش موجودة. من فضلك اعمل /start تاني.", reply_markup=CONTACT_KEYBOARD
        )
        return REQUEST_PHONE

    await update.message.reply_text("لو عايز تشوف تقريرك تاني (بعد آخر تحديث)، ابعت /start.")
    return WAIT_FOR_CUSTOMER_MESSAGE


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("تم الإلغاء. ابعت /start للتحقق تاني.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("مش فاهم الأمر ده. ابعت /start للبدء.")
