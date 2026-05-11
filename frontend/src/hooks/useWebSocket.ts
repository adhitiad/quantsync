"use client";

import { useAuthStore } from "@/store/authStore";
import { useSignalStore } from "@/store/signalStore";
import { SignalResponse } from "@/types/signal";
import { useCallback, useEffect, useRef } from "react";

export const useWebSocket = (url: string) => {
  const token = useAuthStore((state) => state.token);
  const addSignal = useSignalStore((state) => state.addSignal);
  const setConnected = useSignalStore((state) => state.setConnected);
  const wsRef = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    if (!token || !url) return;

    const wsUrl = `${url}?token=${token}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      console.log("WebSocket Connected");
    };

    ws.onmessage = (event) => {
      try {
        const signal: SignalResponse = JSON.parse(event.data);
        addSignal(signal);
      } catch (error) {
        console.error("Error parsing signal data:", error);
      }
    };

    ws.onclose = () => {
      setConnected(false);
    };

    ws.onerror = (error) => {
      console.error("WebSocket Error:", error);
      ws.close();
    };
  }, [url, token, addSignal, setConnected]);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
    };
  }, [connect]);
};
