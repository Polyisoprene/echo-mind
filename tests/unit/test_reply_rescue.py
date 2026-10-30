

def test_rescue_payload_is_loggable() -> None:
    from echomind.runtime.reply_rescue import rescue_payload_json

    assert "知道啊" in rescue_payload_json("知道啊")
