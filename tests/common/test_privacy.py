from common.privacy import mask_email


def test_mask_email_keeps_two_letters_and_the_domain():
    assert mask_email("ioannis@example.com") == "io***@example.com"


def test_mask_email_without_at_sign():
    assert mask_email("x") == "x***@"
