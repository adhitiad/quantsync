"use client";

import SignalTable from "@/components/SignalTable";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useAuthStore } from "@/store/authStore";
import { useSignalStore } from "@/store/signalStore";

export default function DashboardPage() {
  const token = useAuthStore((state) => state.token);
  const { signals, isConnected } = useSignalStore();

  // Koneksi WebSocket hanya jika ada token
  const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8080/ws";
  if (token) {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    useWebSocket(wsUrl);
  }

  if (!token) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p>You are not authenticated. Please login first.</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100 p-8">
      <div className="max-w-7xl mx-auto">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-3xl font-bold">QuantSync Trading Signals</h1>
          <div className="flex items-center">
            <span
              className={`inline-block w-3 h-3 rounded-full mr-2 ${isConnected ? "bg-green-500" : "bg-red-500"}`}
            ></span>
            <span className="text-sm text-gray-600">
              {isConnected ? "Connected" : "Disconnected"}
            </span>
          </div>
        </div>
        <div className="bg-white shadow overflow-hidden sm:rounded-lg">
          <SignalTable signals={signals} />
        </div>
      </div>
    </div>
  );
}
