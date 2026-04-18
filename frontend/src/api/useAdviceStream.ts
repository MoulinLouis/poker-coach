import { useCallback, useEffect, useRef, useState } from "react";
import { fetchEventSource } from "@microsoft/fetch-event-source";
import type { Advice } from "./types";

export type StreamStatus =
  | "idle"
  | "connecting"
  | "thinking"
  | "streaming"
  | "done"
  | "error";

export interface StreamState {
  status: StreamStatus;
  reasoning: string;
  advice: Advice | null;
  costUsd: number | null;
  errorMessage: string | null;
  terminalStatus: string | null;
}

const INITIAL: StreamState = {
  status: "idle",
  reasoning: "",
  advice: null,
  costUsd: null,
  errorMessage: null,
  terminalStatus: null,
};

export function useAdviceStream(): {
  state: StreamState;
  start: (decisionId: string) => void;
  cancel: () => void;
  reset: () => void;
} {
  const [state, setState] = useState<StreamState>(INITIAL);
  const controllerRef = useRef<AbortController | null>(null);

  const cancel = useCallback(() => {
    controllerRef.current?.abort();
    controllerRef.current = null;
  }, []);

  const reset = useCallback(() => {
    cancel();
    setState(INITIAL);
  }, [cancel]);

  const start = useCallback(
    (decisionId: string) => {
      cancel();
      const controller = new AbortController();
      controllerRef.current = controller;
      setState({ ...INITIAL, status: "thinking" });

      fetchEventSource(`/api/decisions/${decisionId}/stream`, {
        signal: controller.signal,
        openWhenHidden: true,
        onmessage(msg) {
          try {
            const payload = JSON.parse(msg.data);
            if (msg.event === "reasoning_delta") {
              setState((s) => ({
                ...s,
                status: "streaming",
                reasoning: s.reasoning + (payload.text ?? ""),
              }));
            } else if (msg.event === "reasoning_complete") {
              setState((s) => ({ ...s, reasoning: payload.full_text ?? s.reasoning }));
            } else if (msg.event === "tool_call_complete") {
              setState((s) => ({ ...s, advice: payload.advice }));
            } else if (msg.event === "usage_complete") {
              setState((s) => ({ ...s, costUsd: payload.cost_usd }));
            } else if (msg.event === "oracle_error") {
              setState((s) => ({
                ...s,
                status: "error",
                errorMessage: payload.message ?? "oracle error",
              }));
            } else if (msg.event === "done") {
              setState((s) => ({
                ...s,
                status: s.status === "error" ? "error" : "done",
                terminalStatus: payload.status ?? "ok",
              }));
            }
          } catch (err) {
            setState((s) => ({
              ...s,
              status: "error",
              errorMessage: `parse error: ${String(err)}`,
            }));
          }
        },
        onerror(err) {
          setState((s) => ({
            ...s,
            status: "error",
            errorMessage: `stream error: ${String(err)}`,
          }));
          throw err; // stop the retry loop
        },
      }).catch(() => {
        /* Swallow — onerror already set state. */
      });
    },
    [cancel],
  );

  useEffect(() => {
    return () => cancel();
  }, [cancel]);

  return { state, start, cancel, reset };
}
