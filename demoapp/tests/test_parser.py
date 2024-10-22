from sendmail.parser import process_template


def test_parse():
    assert sorted(process_template('test/parse_test.html')) == sorted(
        ['place1', 'place_true', 'place_false', 'place_loop',
         'inner', 'inner_true', 'place_block'])
