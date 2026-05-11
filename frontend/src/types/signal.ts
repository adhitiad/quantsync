export interface SignalResponse {
  id_signal: string;
  no: number;
  asset: string;
  price: number;
  action: string; // "buy" or "sell"
  type_action: string; // "limit/stop/market/hold"
  type_signal: string; // "long" or "short"
  tp1: number;
  tp2: number;
  sl1: number;
  sl2: number;
  probability_pct: number;
  winrate_pct: number;
  reason: string;
  timestamp: string;
}
