import { SignalResponse } from "@/types/signal";
import { create } from "zustand";

interface SignalState {
  signals: SignalResponse[];
  isConnected: boolean;
  addSignal: (signal: SignalResponse) => void;
  setConnected: (connected: boolean) => void;
  clearSignals: () => void;
}

export const useSignalStore = create<SignalState>((set) => ({
  signals: [],
  isConnected: false,
  addSignal: (signal) =>
    set((state) => ({
      signals: [signal, ...state.signals].slice(0, 100), // batasi 100 sinyal
    })),
  setConnected: (connected) => set({ isConnected: connected }),
  clearSignals: () => set({ signals: [] }),
}));
