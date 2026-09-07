import { act, renderHook } from "@testing-library/react";
import { useAutosave } from "../src/workspace/useAutosave";

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());
const advance = (time: number) => act(() => vi.advanceTimersByTimeAsync(time));

test("debounces edits while polling renders use the latest callback without restarting the timer", async () => {
  const original = vi.fn(), latest = vi.fn();
  const props = { enabled: true, paused: false, revision: 1, acknowledged: 0, save: original };
  const state = renderHook(useAutosave, { initialProps: props });
  await advance(1500); state.rerender({ ...props, revision: 2 });
  await advance(1500); expect(original).not.toHaveBeenCalled();
  state.rerender({ ...props, revision: 2, save: latest });
  await advance(500); expect(latest).toHaveBeenCalledTimes(1); expect(original).not.toHaveBeenCalled();
  await advance(10000); expect(latest).toHaveBeenCalledTimes(1);
});

test.each(["paused", "disabled", "acknowledged", "unmounted"])("%s cancels a scheduled save", async reason => {
  const save = vi.fn(), props = { enabled: true, paused: false, revision: 1, acknowledged: 0, save };
  const state = renderHook(useAutosave, { initialProps: props });
  await advance(1500);
  if (reason === "unmounted") state.unmount();
  else state.rerender({ ...props, paused: reason === "paused", enabled: reason !== "disabled", acknowledged: reason === "acknowledged" ? 1 : 0 });
  await advance(5000); expect(save).not.toHaveBeenCalled();
});

test("re-enabling dirty work and acknowledging an older in-flight revision each schedule only the latest work", async () => {
  const save = vi.fn(), props = { enabled: false, paused: false, revision: 1, acknowledged: 0, save };
  const state = renderHook(useAutosave, { initialProps: props });
  await advance(5000); expect(save).not.toHaveBeenCalled();
  state.rerender({ ...props, enabled: true }); await advance(2000); expect(save).toHaveBeenCalledTimes(1);
  state.rerender({ ...props, enabled: true, paused: true, revision: 2 }); await advance(3000); expect(save).toHaveBeenCalledTimes(1);
  state.rerender({ ...props, enabled: true, revision: 2, acknowledged: 1 }); await advance(2000); expect(save).toHaveBeenCalledTimes(2);
  state.rerender({ ...props, enabled: true, revision: 2, acknowledged: 2 }); await advance(10000); expect(save).toHaveBeenCalledTimes(2);
});
