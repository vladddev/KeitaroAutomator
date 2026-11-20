import { useEffect, useState } from "react";
import type { OfferItem, Stream } from "../types";
import { OfferSearchSelect } from "./OfferSearchSelect";

interface StreamCardProps {
  stream: Stream;
  busy: boolean;
  onAddOffer: (streamId: number, offerId: number) => Promise<void>;
  onRemoveOffer: (streamId: number, offerKeitaroId: number) => Promise<void>;
  onBringBackOffer: (streamId: number, offerKeitaroId: number) => Promise<void>;
  onPinOffer: (
    streamId: number,
    offerKeitaroId: number,
    isPinned: boolean,
    share?: number
  ) => Promise<void>;
  onPush: (streamId: number) => Promise<void>;
  onCancel: (streamId: number) => Promise<void>;
}

export function StreamCard({
  stream,
  busy,
  onAddOffer,
  onRemoveOffer,
  onBringBackOffer,
  onPinOffer,
  onPush,
  onCancel,
}: StreamCardProps) {
  const [offerToAdd, setOfferToAdd] = useState<OfferItem | null>(null);
  const [shareInputs, setShareInputs] = useState<Record<number, string>>({});

  useEffect(() => {
    const next: Record<number, string> = {};
    for (const offer of stream.offers) {
      next[offer.offer_keitaro_id] = String(offer.draft_share);
    }
    setShareInputs(next);
  }, [stream.offers]);

  if (!stream.has_offers) {
    return (
      <div className="card stream-card stream-card--stub">
        <div className="stream-card__header">
          <div>
            <span className="badge badge--neutral">Позиция {stream.position}</span>{" "}
            <strong>{stream.name}</strong>{" "}
            <span className="muted">(Keitaro ID: {stream.keitaro_id})</span>
          </div>
          <span className="badge badge--neutral">
            Поток без офферов (редирект / фильтры, схема: {stream.schema_name || "action"})
          </span>
        </div>
      </div>
    );
  }

  const handleAdd = async () => {
    if (!offerToAdd) return;
    await onAddOffer(stream.id, offerToAdd.id);
    setOfferToAdd(null);
  };

  const handleApplyPin = async (offerKeitaroId: number) => {
    const raw = shareInputs[offerKeitaroId] ?? "";
    const parsed = Number(raw);
    if (!Number.isInteger(parsed) || parsed < 0 || parsed > 100) {
      return;
    }
    await onPinOffer(stream.id, offerKeitaroId, true, parsed);
  };

  return (
    <div
      className={`card stream-card ${stream.is_dirty ? "stream-card--dirty" : "stream-card--clean"}`}
    >
      <div className="stream-card__header">
        <div className="stream-card__title">
          <span className="badge badge--neutral">Позиция {stream.position}</span>
          <h3>{stream.name}</h3>
          <span className="muted">Keitaro ID: {stream.keitaro_id}</span>
          {stream.is_dirty ? (
            <span className="badge badge--warning">Не опубликовано</span>
          ) : (
            <span className="badge badge--success">Синхронизировано</span>
          )}
        </div>

        <div className="stream-card__actions">
          <button
            type="button"
            className="btn btn--ghost"
            disabled={!stream.is_dirty || busy}
            onClick={() => void onCancel(stream.id)}
          >
            Отменить
          </button>
          <button
            type="button"
            className="btn btn--primary"
            disabled={!stream.is_dirty || !stream.can_push || busy}
            onClick={() => void onPush(stream.id)}
          >
            Опубликовать в Keitaro
          </button>
        </div>
      </div>

      <div className="stream-add-bar">
        <div className="stream-add-bar__search">
          <OfferSearchSelect
            value={offerToAdd}
            onChange={setOfferToAdd}
            disabled={busy}
            placeholder="Найти оффер по ID или названию для добавления..."
          />
        </div>
        <button
          type="button"
          className="btn btn--secondary"
          disabled={!offerToAdd || busy}
          onClick={() => void handleAdd()}
        >
          Добавить оффер
        </button>
      </div>

      <div className="table-wrap">
        <table className="offers-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Оффер</th>
              <th>Статус</th>
              <th>Вес %</th>
              <th>Фиксация</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {stream.offers.length === 0 && (
              <tr>
                <td colSpan={6} className="muted text-center">
                  В этом потоке пока нет офферов
                </td>
              </tr>
            )}
            {stream.offers.map((offer) => {
              const isRemoved = offer.draft_status === "removed";
              const currentInput = shareInputs[offer.offer_keitaro_id] ?? String(offer.draft_share);
              const inputChanged = Number(currentInput) !== offer.draft_share;

              return (
                <tr
                  key={offer.offer_keitaro_id}
                  className={isRemoved ? "offer-row--removed" : ""}
                >
                  <td>#{offer.offer_keitaro_id}</td>
                  <td>
                    <span>{offer.offer_name}</span>
                    {offer.published_status === null && (
                      <span className="badge badge--info ml-2">Новый</span>
                    )}
                  </td>
                  <td>
                    {isRemoved ? (
                      <span className="badge badge--neutral">Удален (архив)</span>
                    ) : (
                      <span className="badge badge--success">Активен</span>
                    )}
                  </td>
                  <td>
                    {isRemoved ? (
                      <span className="muted">0%</span>
                    ) : (
                      <div className="weight-cell">
                        <input
                          type="number"
                          min={0}
                          max={100}
                          step={1}
                          className="weight-input"
                          disabled={busy}
                          value={currentInput}
                          onChange={(e) =>
                            setShareInputs((prev) => ({
                              ...prev,
                              [offer.offer_keitaro_id]: e.target.value,
                            }))
                          }
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              e.preventDefault();
                              void handleApplyPin(offer.offer_keitaro_id);
                            }
                          }}
                        />
                        <span>%</span>
                        {inputChanged && (
                          <button
                            type="button"
                            className="btn btn--secondary btn--sm"
                            disabled={busy}
                            onClick={() => void handleApplyPin(offer.offer_keitaro_id)}
                          >
                            Задать
                          </button>
                        )}
                      </div>
                    )}
                  </td>
                  <td>
                    {!isRemoved && (
                      <button
                        type="button"
                        className={`btn btn--sm ${
                          offer.draft_is_pinned ? "btn--pin-active" : "btn--ghost"
                        }`}
                        disabled={busy}
                        onClick={() =>
                          offer.draft_is_pinned
                            ? void onPinOffer(stream.id, offer.offer_keitaro_id, false)
                            : void handleApplyPin(offer.offer_keitaro_id)
                        }
                      >
                        {offer.draft_is_pinned ? "Закреплен (снять)" : "Закрепить"}
                      </button>
                    )}
                  </td>
                  <td>
                    {isRemoved ? (
                      <button
                        type="button"
                        className="btn btn--secondary btn--sm"
                        disabled={busy}
                        onClick={() => void onBringBackOffer(stream.id, offer.offer_keitaro_id)}
                      >
                        Вернуть
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="btn btn--danger btn--sm"
                        disabled={busy}
                        onClick={() => void onRemoveOffer(stream.id, offer.offer_keitaro_id)}
                      >
                        Удалить
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="stream-card__footer">
        <div
          className={`total-share ${
            stream.total_active_share === 100 ? "total-share--ok" : "total-share--bad"
          }`}
        >
          Сумма активных весов: {stream.total_active_share}%
        </div>
        {stream.validation_errors.length > 0 && (
          <div className="alert alert--error mt-2">{stream.validation_errors.join(". ")}</div>
        )}
      </div>
    </div>
  );
}
