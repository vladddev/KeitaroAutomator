import { KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";

export interface SelectOption {
  id: number;
  name: string;
  sublabel?: string;
}

interface SearchableSelectProps {
  inputId?: string;
  options: SelectOption[];
  value: number | null;
  onChange: (value: number | null) => void;
  placeholder?: string;
  emptyOptionLabel?: string;
  disabled?: boolean;
}

const MAX_RENDERED_OPTIONS = 100;

export function SearchableSelect({
  inputId,
  options,
  value,
  onChange,
  placeholder = "Начните вводить для поиска...",
  emptyOptionLabel,
  disabled = false,
}: SearchableSelectProps) {
  const [open, setOpen] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);

  const rootRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const selectedOption = useMemo(
    () => options.find((opt) => opt.id === value) ?? null,
    [options, value]
  );

  useEffect(() => {
    const handleOutside = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false);
        setIsTyping(false);
        setQuery("");
      }
    };
    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, []);

  const trimmedQuery = isTyping ? query.trim().toLowerCase() : "";

  const filteredOptions = useMemo(() => {
    if (!trimmedQuery) {
      return options;
    }
    const matched = options.filter((opt) => {
      if (String(opt.id).includes(trimmedQuery)) return true;
      if (opt.name.toLowerCase().includes(trimmedQuery)) return true;
      if (opt.sublabel && opt.sublabel.toLowerCase().includes(trimmedQuery)) return true;
      return false;
    });
    matched.sort((a, b) => {
      const aExact = String(a.id) === trimmedQuery ? 0 : 1;
      const bExact = String(b.id) === trimmedQuery ? 0 : 1;
      return aExact - bExact;
    });
    return matched;
  }, [options, trimmedQuery]);

  const showEmptyOption =
    Boolean(emptyOptionLabel) &&
    (!trimmedQuery || emptyOptionLabel!.toLowerCase().includes(trimmedQuery));

  const renderedOptions = filteredOptions.slice(0, MAX_RENDERED_OPTIONS);

  const selectableEntries = useMemo(() => {
    const entries: Array<
      { kind: "empty" } | { kind: "option"; option: SelectOption }
    > = [];
    if (showEmptyOption) {
      entries.push({ kind: "empty" });
    }
    for (const option of renderedOptions) {
      entries.push({ kind: "option", option });
    }
    return entries;
  }, [showEmptyOption, renderedOptions]);

  const displayValue = isTyping
    ? query
    : selectedOption
      ? `#${selectedOption.id} - ${selectedOption.name}`
      : "";

  const selectValue = (nextValue: number | null) => {
    onChange(nextValue);
    setOpen(false);
    setIsTyping(false);
    setQuery("");
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (disabled) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (!open) {
        setOpen(true);
        setActiveIndex(0);
        return;
      }
      if (selectableEntries.length > 0) {
        setActiveIndex((prev) => (prev + 1) % selectableEntries.length);
      }
      return;
    }

    if (e.key === "ArrowUp") {
      e.preventDefault();
      if (!open) {
        setOpen(true);
        setActiveIndex(0);
        return;
      }
      if (selectableEntries.length > 0) {
        setActiveIndex(
          (prev) => (prev - 1 + selectableEntries.length) % selectableEntries.length
        );
      }
      return;
    }

    if (e.key === "Enter" && open && selectableEntries.length > 0) {
      e.preventDefault();
      const idx = Math.min(activeIndex, selectableEntries.length - 1);
      const entry = selectableEntries[idx];
      if (entry.kind === "empty") {
        selectValue(null);
      } else {
        selectValue(entry.option.id);
      }
      return;
    }

    if (e.key === "Escape") {
      setOpen(false);
      setIsTyping(false);
      setQuery("");
    }
  };

  return (
    <div
      className={`searchable-select ${disabled ? "searchable-select--disabled" : ""}`}
      ref={rootRef}
    >
      <div className="searchable-select__control">
        <input
          ref={inputRef}
          id={inputId}
          type="text"
          role="combobox"
          aria-expanded={open}
          aria-autocomplete="list"
          className="searchable-select__input"
          value={displayValue}
          disabled={disabled}
          placeholder={emptyOptionLabel || placeholder}
          autoComplete="off"
          onFocus={(e) => {
            if (disabled) return;
            setOpen(true);
            setIsTyping(false);
            setQuery("");
            setActiveIndex(0);
            e.currentTarget.select();
          }}
          onChange={(e) => {
            setIsTyping(true);
            setQuery(e.target.value);
            setOpen(true);
            setActiveIndex(0);
          }}
          onKeyDown={handleKeyDown}
        />

        <div className="searchable-select__actions">
          {value !== null && emptyOptionLabel && !disabled && (
            <button
              type="button"
              className="searchable-select__icon-btn"
              title="Сбросить выбор"
              aria-label="Сбросить выбор"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => selectValue(null)}
            >
              ×
            </button>
          )}
          <button
            type="button"
            className="searchable-select__icon-btn"
            disabled={disabled}
            aria-label={open ? "Скрыть список" : "Открыть список"}
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => {
              if (disabled) return;
              if (open) {
                setOpen(false);
                setIsTyping(false);
                setQuery("");
              } else {
                setIsTyping(false);
                setQuery("");
                setActiveIndex(0);
                setOpen(true);
                inputRef.current?.focus();
              }
            }}
          >
            ▾
          </button>
        </div>
      </div>

      {open && !disabled && (
        <div className="searchable-select__dropdown" role="listbox">
          {selectableEntries.length === 0 ? (
            <div className="searchable-select__meta">Ничего не найдено</div>
          ) : (
            selectableEntries.map((entry, idx) => {
              const isActive = idx === activeIndex;
              if (entry.kind === "empty") {
                return (
                  <button
                    key="__empty__"
                    type="button"
                    role="option"
                    aria-selected={value === null}
                    className={`searchable-select__item ${
                      isActive ? "searchable-select__item--active" : ""
                    } ${value === null ? "searchable-select__item--selected" : ""}`}
                    onMouseDown={(e) => e.preventDefault()}
                    onMouseEnter={() => setActiveIndex(idx)}
                    onClick={() => selectValue(null)}
                  >
                    <span className="muted">{emptyOptionLabel}</span>
                  </button>
                );
              }

              const opt = entry.option;
              const isSelected = opt.id === value;
              return (
                <button
                  key={opt.id}
                  type="button"
                  role="option"
                  aria-selected={isSelected}
                  className={`searchable-select__item ${
                    isActive ? "searchable-select__item--active" : ""
                  } ${isSelected ? "searchable-select__item--selected" : ""}`}
                  onMouseDown={(e) => e.preventDefault()}
                  onMouseEnter={() => setActiveIndex(idx)}
                  onClick={() => selectValue(opt.id)}
                >
                  <span className="offer-id">#{opt.id}</span>
                  <span className="offer-name">{opt.name}</span>
                  {opt.sublabel && (
                    <span className="searchable-select__sublabel">{opt.sublabel}</span>
                  )}
                </button>
              );
            })
          )}
          {filteredOptions.length > MAX_RENDERED_OPTIONS && (
            <div className="searchable-select__meta">
              Показаны первые {MAX_RENDERED_OPTIONS} из {filteredOptions.length}, уточните запрос
            </div>
          )}
        </div>
      )}
    </div>
  );
}
