import { KeyboardEvent, useEffect, useRef, useState } from "react";
import { ApiError, api } from "../api/client";
import type { OfferItem } from "../types";

interface OfferSearchSelectProps {
  value: OfferItem | null;
  onChange: (offer: OfferItem | null) => void;
  placeholder?: string;
  disabled?: boolean;
  inputId?: string;
}

export function OfferSearchSelect({
  value,
  onChange,
  placeholder = "Поиск оффера по ID или названию...",
  disabled = false,
  inputId,
}: OfferSearchSelectProps) {
  const [query, setQuery] = useState(value ? `#${value.id} - ${value.name}` : "");
  const [items, setItems] = useState<OfferItem[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (value) {
      setQuery(`#${value.id} - ${value.name}`);
    } else {
      setQuery("");
    }
  }, [value]);

  useEffect(() => {
    const handleOutside = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, []);

  const fetchOffers = async (searchText: string, refresh = false) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.searchOffers(searchText, refresh);
      setItems(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Ошибка загрузки офферов");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!open) return;
    const isFormattedSelected =
      value !== null && query.trim() === `#${value.id} - ${value.name}`;
    const effectiveQuery = isFormattedSelected ? "" : query;
    const timer = window.setTimeout(() => {
      void fetchOffers(effectiveQuery);
    }, 220);
    return () => window.clearTimeout(timer);
  }, [query, open, value]);

  const handleSelect = (item: OfferItem) => {
    onChange(item);
    setQuery(`#${item.id} - ${item.name}`);
    setOpen(false);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key !== "Enter") return;
    if (!open && items.length === 0) return;

    const trimmed = query.trim();
    const numericId = Number(trimmed);
    if (/^\d+$/.test(trimmed) && numericId > 0) {
      e.preventDefault();
      const matched = items.find((o) => o.id === numericId);
      handleSelect(matched ?? { id: numericId, name: `Offer #${numericId}`, state: null });
      return;
    }

    if (items.length > 0 && open) {
      e.preventDefault();
      handleSelect(items[0]);
    }
  };

  return (
    <div className="offer-search" ref={rootRef}>
      <div className="input-row">
        <input
          id={inputId}
          type="text"
          value={query}
          disabled={disabled}
          placeholder={placeholder}
          onFocus={() => setOpen(true)}
          onChange={(e) => {
            setQuery(e.target.value);
            if (value !== null) {
              onChange(null);
            }
            setOpen(true);
          }}
          onKeyDown={handleKeyDown}
        />
        {value && !disabled && (
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            onClick={() => {
              onChange(null);
              setQuery("");
              setOpen(true);
            }}
          >
            Очистить
          </button>
        )}
        <button
          type="button"
          className="btn btn--ghost btn--sm"
          disabled={disabled || loading}
          title="Обновить кэш офферов из Keitaro"
          onClick={() => {
            setOpen(true);
            void fetchOffers(value ? "" : query, true);
          }}
        >
          Обновить
        </button>
      </div>

      {open && !disabled && (
        <div className="offer-dropdown">
          {loading && <div className="offer-dropdown__state">Загрузка офферов...</div>}
          {!loading && error && <div className="offer-dropdown__error">{error}</div>}
          {!loading && !error && items.length === 0 && (
            <div className="offer-dropdown__state">Офферы не найдены</div>
          )}
          {!loading &&
            !error &&
            items.map((item) => (
              <button
                key={item.id}
                type="button"
                className="offer-dropdown__item"
                onClick={() => handleSelect(item)}
              >
                <span className="offer-id">#{item.id}</span>
                <span className="offer-name">{item.name}</span>
                {item.state && <span className="badge badge--neutral">{item.state}</span>}
              </button>
            ))}
        </div>
      )}
    </div>
  );
}
