from app.services.report_formatting import format_commission_report

# a real row from Fcc_Commission_New.xlsx (Master 1153420)
SAMPLE_ROW = {
    "Master": 1153420, "Gov": "الدقهلية", "Area": "ثان المنصورة", "Rep": "Mohammed.A.Hammad",
    "SV": "Saad.Temraz", "MGR": "mohamed.m.othmaan", "Category": "Super X",
    "Target 293": 4187644.0347777777, "293 MTD": 461650, "293 Expected Closing": 461650,
    "%": 0.11024098423028882,
    "Airtime MTD": 6375231, "Airtime Expected Closing": 6375231,
    "T 1 G 10%": 7693670.545, "T 2 G 15%": 8043382.8425, "T 3 G 20%": 8393095.14,
    "Bills MTD": 23671602.35, "Bills Expected Closing": 23671602.35,
    "MFI MTD": 10502219, "MFI Expected Closing": 10502219,
    "Fawry Pay MTD": 5222132.65, "Fawry Pay Expected Closing": 5222132.65,
    "Cashout MTD": 5295900, "Cashout Closing": 5295900,
    "293 Bonus": 0, "Commission 10 %": 0, "Commission 15 %": 0, "Commission 20 %": 0,
    "Total Airtime Commission": 0, "Extra Bouns Cash Out": 10591.8,
    "MFI Deduction": 0, "Fawry pay Deduction": 0, "Net Bonus/Penalty": 10591.8,
    "240 MTD": 35744988, "Total Transfer Target": 60971164.8, "Total Transfer MTD": 36206638,
    "Expected Transfer": 36206638, "%2": 0.5938321519486537, "Tiers": "More 650K",
}


def test_text_fields_are_shown_verbatim():
    text = format_commission_report(SAMPLE_ROW)
    assert "<b>Master</b>: 1153420" in text
    assert "<b>Gov</b>: الدقهلية" in text
    assert "<b>Rep</b>: Mohammed.A.Hammad" in text
    assert "<b>Tiers</b>: More 650K" in text


def test_percent_fields_are_rounded_whole_percent():
    text = format_commission_report(SAMPLE_ROW)
    assert "<b>%</b>: 11%" in text
    assert "<b>%2</b>: 59%" in text


def test_money_fields_are_comma_formatted_and_rounded():
    text = format_commission_report(SAMPLE_ROW)
    assert "<b>Target 293</b>: 4,187,644" in text
    assert "<b>Bills MTD</b>: 23,671,602" in text
    assert "<b>Extra Bouns Cash Out</b>: 10,592" in text


def test_zero_values_are_shown_as_dash_not_zero():
    text = format_commission_report(SAMPLE_ROW)
    assert "<b>293 Bonus</b>: -" in text
    assert "<b>Commission 10 %</b>: -" in text
    assert "<b>MFI Deduction</b>: -" in text
    assert "<b>293 Bonus</b>: 0" not in text


def test_field_order_matches_the_sheet():
    text = format_commission_report(SAMPLE_ROW)
    master_pos = text.index("Master")
    gov_pos = text.index("Gov")
    tiers_pos = text.index("Tiers")
    assert master_pos < gov_pos < tiers_pos
