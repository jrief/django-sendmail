from sendmail.mixins import SwappableMetaMixin


def test_swappable_meta_mixin():
    class SwappableUser(SwappableMetaMixin):
        pass

    assert SwappableUser.Meta.swappable == 'sendmail.EmailAddress'
