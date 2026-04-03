import CryptoDetailClient from "./client";

const TOP_SYMBOLS = [
  "BTC","ETH","SOL","BNB","XRP","ADA","DOGE","AVAX","DOT","MATIC",
  "LINK","UNI","ATOM","LTC","NEAR","APT","ARB","OP","FIL","AAVE",
  "SHIB","TRX","TON","SUI","SEI","PEPE","WLD","INJ","TIA","JUP",
  "ONDO","RENDER","FET","STX","IMX","MKR","GRT","ALGO","FTM","SAND",
  "MANA","AXS","THETA","EGLD","FLOW","XLM","VET","HBAR","EOS","CRO",
];

export function generateStaticParams() {
  return TOP_SYMBOLS.map((s) => ({ symbol: s }));
}

export default function Page() {
  return <CryptoDetailClient />;
}
