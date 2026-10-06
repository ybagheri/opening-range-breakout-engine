from orb_engine.persistence.journal import TradeJournal
from orb_engine.persistence.state import StateStore


def test_state_idempotency(tmp_path):
    st = StateStore(str(tmp_path/"s.db"))
    assert not st.already_traded("US30","2024-01-02")
    st.mark_traded("US30","2024-01-02",123,"LONG")
    assert st.already_traded("US30","2024-01-02")
    assert st.get("US30","2024-01-02")["ticket"] == 123

def test_journal_roundtrip(tmp_path):
    j = TradeJournal(str(tmp_path/"j.db"))
    j.record({"trade_id":"a","symbol":"US30","direction":"LONG","session_date":"2024-01-02",
      "or_high":1,"or_low":0,"signal_time":"t","entry_time":"t","entry_price":1,"stop_price":0,
      "target_price":2,"volume":0.1,"risk_pct":0.5,"risk_amount":50,"exit_time":"t","exit_price":2,
      "exit_reason":"TAKE_PROFIT","gross_pnl":10,"commission":0,"swap":0,"net_pnl":10,
      "r_multiple":2.0,"breakeven_used":True,"config_hash":"abc","extra":{}})
    assert len(j.all()) == 1
