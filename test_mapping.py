"""Checks for transparent financial label mapping and number parsing."""

from src.mapping import normalise_label, parse_number, suggest_field


def test_common_financial_labels_map_to_readable_fields():
    assert suggest_field("Sales from operations")[0] == "revenue"
    assert suggest_field("Profit after tax")[0] == "net_profit"
    assert suggest_field("Current liabilities")[0] == "current_liabilities"


def test_unknown_label_is_left_unmapped():
    assert suggest_field("Employee happiness index") == (None, "unmapped")


def test_alias_and_number_parsing():
    assert normalise_label("Net-Profit (%)") == "netprofit"
    assert parse_number("(1,250)") == -1250
    assert parse_number("₹ 2,500") == 2500
    assert parse_number("N/A") is None
