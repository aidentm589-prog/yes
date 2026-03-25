"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";

export function LiveRunController({
  runId,
  status,
}: {
  runId: string;
  status: string;
}) {
  const router = useRouter();
  const inFlight = useRef(false);
  const stopped = useRef(false);

  useEffect(() => {
    const refreshTimer = window.setInterval(() => {
      router.refresh();
    }, 3_000);

    return () => {
      window.clearInterval(refreshTimer);
    };
  }, [router]);

  useEffect(() => {
    if (!["queued", "running"].includes(status) || inFlight.current || stopped.current) {
      return;
    }

    inFlight.current = true;
    fetch(`/api/runs/${runId}/continue`, {
      method: "POST",
    })
      .then((response) => {
        if (!response.ok) {
          stopped.current = true;
        }
      })
      .catch(() => {
        stopped.current = true;
      })
      .finally(() => {
        inFlight.current = false;
        router.refresh();
      });
  }, [runId, router, status]);

  return null;
}
