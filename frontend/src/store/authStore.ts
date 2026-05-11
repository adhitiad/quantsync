import { create } from "zustand";

interface AuthState {
  token: string | null;
  username: string | null;
  role: string | null;
  plan: string | null;
  setAuth: (
    token: string,
    username: string,
    role: string,
    plan: string,
  ) => void;
  clearAuth: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  username: null,
  role: null,
  plan: null,
  setAuth: (token, username, role, plan) =>
    set({ token, username, role, plan }),
  clearAuth: () => set({ token: null, username: null, role: null, plan: null }),
}));
