from glory_hype.narrative.adapters.social import SocialAdapter


def test_social_stub_returns_empty():
    a = SocialAdapter()
    assert a.source == "social"
    assert a.fetch() == []
