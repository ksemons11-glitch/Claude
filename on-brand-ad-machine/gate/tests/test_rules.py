from gate.rules import check_text


def ids(rep):
    return set(v.rule_id for v in rep.violations)


def test_clean_brief_copy_passes():
    rep = check_text("Naklej VeluSkin na noc dokładnie tam, gdzie linie najbardziej Ci przeszkadzają. "
                     "16 wielorazowych plastrów ze 100% silikonu.")
    assert not rep.hard_fail, rep.summary()


def test_100_percent_silicone_is_exempt_but_other_percent_is_not():
    assert not check_text("100% silikon").hard_fail
    rep = check_text("87% zauważyło mniejszą widoczność zmarszczek")
    assert "C5/K19" in ids(rep)


def test_percent_with_survey_wording_is_allowed():
    rep = check_text("W ankiecie naszych klientek 87% zauważyło mniejszą widoczność zmarszczek")
    assert "C5/K19" not in ids(rep)


def test_banned_claims():
    assert "C8/K12" in ids(check_text("Widoczny efekt już od 1. nocy"))
    assert "C8/K12" in ids(check_text("wygładza już po pierwszym użyciu"))
    assert "C8/K11" in ids(check_text("Bezpieczne w ciąży i podczas karmienia"))
    assert "C3/K10" in ids(check_text("silikon klasy medycznej"))
    assert "C4/K13" in ids(check_text("Botoks boli. VeluSkin to alternatywa"))
    assert "C6/K20-21" in ids(check_text("Dziś -45% i darmowa dostawa"))
    assert "C15/K23" in ids(check_text("Pozbądź się pionowych zmarszczek"))
    assert "K25" in ids(check_text("przez sen wygładza i napina skórę"))
    assert "C7/K22" in ids(check_text("dermatolodzy polecają"))
    assert "C2" in ids(check_text("Zamów teraz!"))


def test_brand_spelling():
    assert "C12" in ids(check_text("Plastry Veluskin"))
    assert "C12" not in ids(check_text("Plastry VeluSkin"))


def test_length_rules_are_should():
    rep = check_text("x", headline="jeden dwa trzy cztery pięć sześć siedem osiem dziewięć dziesięć jedenaście dwanaście trzynaście")
    assert "C18" in rep.should_ids and not rep.hard_fail
