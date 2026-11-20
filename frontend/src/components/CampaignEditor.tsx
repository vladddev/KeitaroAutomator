import { useCallback, useEffect, useState } from "react";
import { ApiError, api } from "../api/client";
import type { CampaignSummary, Stream } from "../types";
import { SearchableSelect } from "./SearchableSelect";
import { StreamCard } from "./StreamCard";

interface CampaignEditorProps {
  initialCampaignId: number | null;
}

export function CampaignEditor({ initialCampaignId }: CampaignEditorProps) {
  const [campaigns, setCampaigns] = useState<CampaignSummary[]>([]);
  const [selectedCampaignId, setSelectedCampaignId] = useState<number | null>(initialCampaignId);
  const [streams, setStreams] = useState<Stream[]>([]);

  const [loadingCampaigns, setLoadingCampaigns] = useState(true);
  const [loadingStreams, setLoadingStreams] = useState(false);
  const [busyStreamId, setBusyStreamId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadCampaigns = useCallback(async () => {
    setLoadingCampaigns(true);
    setError(null);
    try {
      const list = await api.getCampaigns();
      setCampaigns(list);
      setSelectedCampaignId((prev) => {
        if (prev !== null) return prev;
        if (initialCampaignId !== null) return initialCampaignId;
        return list.length > 0 ? list[0].id : null;
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось загрузить список кампаний");
    } finally {
      setLoadingCampaigns(false);
    }
  }, [initialCampaignId]);

  useEffect(() => {
    void loadCampaigns();
  }, [loadCampaigns]);

  useEffect(() => {
    if (initialCampaignId !== null) {
      setSelectedCampaignId(initialCampaignId);
    }
  }, [initialCampaignId]);

  const loadLocalStreams = useCallback(async (campaignId: number) => {
    setLoadingStreams(true);
    setError(null);
    try {
      const data = await api.getStreams(campaignId);
      setStreams(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Ошибка загрузки потоков");
    } finally {
      setLoadingStreams(false);
    }
  }, []);

  useEffect(() => {
    if (selectedCampaignId !== null) {
      void loadLocalStreams(selectedCampaignId);
    } else {
      setStreams([]);
    }
  }, [selectedCampaignId, loadLocalStreams]);

  const hasDirtyStreams = streams.some((s) => s.is_dirty);

  const handleFetchStreams = async () => {
    if (selectedCampaignId === null) return;
    if (
      hasDirtyStreams &&
      !window.confirm(
        "Есть неопубликованные черновики (желтые потоки). Загрузка потоков перезапишет их данными из Keitaro. Продолжить?"
      )
    ) {
      return;
    }

    setLoadingStreams(true);
    setError(null);
    try {
      const data = await api.fetchStreams(selectedCampaignId);
      setStreams(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Ошибка синхронизации с Keitaro");
    } finally {
      setLoadingStreams(false);
    }
  };

  const replaceStream = (updated: Stream) => {
    setStreams((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
  };

  const runStreamAction = async (streamId: number, action: () => Promise<Stream>) => {
    setBusyStreamId(streamId);
    setError(null);
    try {
      const updated = await action();
      replaceStream(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Ошибка при обновлении потока");
    } finally {
      setBusyStreamId(null);
    }
  };

  return (
    <div className="stack">
      <div className="card">
        <div className="card__header">
          <div>
            <h2>Редактор кампании</h2>
            <p className="muted">
              Локальное редактирование офферов и весов с черновиками, закреплением, мягким
              удалением, восстановлением и публикацией в Keitaro.
            </p>
          </div>
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            disabled={loadingCampaigns}
            onClick={() => void loadCampaigns()}
          >
            Обновить кампании
          </button>
        </div>

        <div className="editor-toolbar">
          <div className="field editor-toolbar__select">
            <label htmlFor="campaign-select">Кампания в Keitaro</label>
            <SearchableSelect
              inputId="campaign-select"
              options={campaigns.map((c) => ({
                id: c.id,
                name: c.name,
                sublabel: c.alias ?? undefined,
              }))}
              value={selectedCampaignId}
              onChange={setSelectedCampaignId}
              placeholder="Начните вводить ID или название кампании..."
              disabled={loadingCampaigns}
            />
          </div>

          <div className="editor-toolbar__btn">
            <button
              type="button"
              className="btn btn--primary"
              disabled={selectedCampaignId === null || loadingStreams}
              onClick={() => void handleFetchStreams()}
            >
              {loadingStreams ? "Синхронизация..." : "Загрузить потоки"}
            </button>
          </div>
        </div>
      </div>

      {error && <div className="alert alert--error">{error}</div>}

      {selectedCampaignId !== null && !loadingStreams && streams.length === 0 && (
        <div className="card">
          <p className="muted">
            Для кампании #{selectedCampaignId} еще нет загруженных потоков в локальной БД. Нажмите{" "}
            <strong>Загрузить потоки</strong>, чтобы импортировать структуру из Keitaro.
          </p>
        </div>
      )}

      {streams.map((stream) => (
        <StreamCard
          key={stream.id}
          stream={stream}
          busy={busyStreamId === stream.id || loadingStreams}
          onAddOffer={(sid, oid) => runStreamAction(sid, () => api.addOffer(sid, oid))}
          onRemoveOffer={(sid, oid) => runStreamAction(sid, () => api.removeOffer(sid, oid))}
          onBringBackOffer={(sid, oid) =>
            runStreamAction(sid, () => api.bringBackOffer(sid, oid))
          }
          onPinOffer={(sid, oid, pinned, share) =>
            runStreamAction(sid, () => api.pinOffer(sid, oid, pinned, share))
          }
          onPush={(sid) => runStreamAction(sid, () => api.pushStream(sid))}
          onCancel={(sid) => runStreamAction(sid, () => api.cancelStream(sid))}
        />
      ))}
    </div>
  );
}
