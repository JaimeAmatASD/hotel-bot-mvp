"""Telegram send + DB logging — the only place that does actual I/O."""
import storage


async def send_notification_with_logging(
    bot,
    recipient_telegram_id: int,
    actual_recipient_telegram_id: int,
    message: str,
    photo_path: str | None,
    incident_id: int,
    redirect_mode: str,
    reply_markup=None,
) -> None:
    try:
        if photo_path:
            with open(photo_path, "rb") as f:
                await bot.send_photo(
                    chat_id=actual_recipient_telegram_id,
                    photo=f,
                    caption=message,
                    reply_markup=reply_markup,
                )
        else:
            await bot.send_message(
                chat_id=actual_recipient_telegram_id,
                text=message,
                reply_markup=reply_markup,
            )
        storage.save_notification(
            incident_id=incident_id,
            recipient_telegram_id=recipient_telegram_id,
            recipient_actual_telegram_id=actual_recipient_telegram_id,
            redirect_mode=redirect_mode,
            status="sent",
        )
        storage.save_event(
            incident_id=incident_id,
            actor_telegram_id=0,
            actor_name="sistema",
            action="notification_sent",
            success=True,
            extra={
                "recipient": recipient_telegram_id,
                "actual_recipient": actual_recipient_telegram_id,
                "redirect_mode": redirect_mode,
            },
        )
    except Exception as e:
        storage.save_notification(
            incident_id=incident_id,
            recipient_telegram_id=recipient_telegram_id,
            recipient_actual_telegram_id=actual_recipient_telegram_id,
            redirect_mode=redirect_mode,
            status="failed",
            error_message=str(e),
        )
        storage.save_event(
            incident_id=incident_id,
            actor_telegram_id=0,
            actor_name="sistema",
            action="notification_failed",
            success=False,
            reason=str(e),
            extra={"recipient": recipient_telegram_id},
        )
