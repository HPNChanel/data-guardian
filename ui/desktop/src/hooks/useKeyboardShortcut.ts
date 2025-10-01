import { useEffect } from "react";

type Handler = (event: KeyboardEvent) => void;

export function useKeyboardShortcut(keys: string[], handler: Handler, element: Document | HTMLElement = document) {
  useEffect(() => {
    const listener = (event: KeyboardEvent) => {
      const { metaKey, ctrlKey, shiftKey, altKey, key } = event;
      const normalized = [
        metaKey ? "Meta" : null,
        ctrlKey ? "Control" : null,
        altKey ? "Alt" : null,
        shiftKey ? "Shift" : null,
        key.length === 1 ? key.toUpperCase() : key,
      ]
        .filter(Boolean)
        .join("+");

      if (keys.includes(normalized)) {
        event.preventDefault();
        handler(event);
      }
    };

    element.addEventListener("keydown", listener as EventListener);
    return () => element.removeEventListener("keydown", listener as EventListener);
  }, [keys, handler, element]);
}
