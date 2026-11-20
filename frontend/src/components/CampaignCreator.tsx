import { FormEvent, useEffect, useState } from "react";
import { ApiError, api } from "../api/client";
import type { CampaignCreateResult, OfferItem, References } from "../types";
import { OfferSearchSelect } from "./OfferSearchSelect";
import { SearchableSelect } from "./SearchableSelect";

interface CampaignCreatorProps {
  defaultPrefix: string;
  onOpenInEditor: (campaignKeitaroId: number) => void;
}

export function CampaignCreator({ defaultPrefix, onOpenInEditor }: CampaignCreatorProps) {
  const [references, setReferences] = useState<References | null>(null);
  const [refsLoading, setRefsLoading] = useState(true);
  const [refsError, setRefsError] = useState<string | null>(null);

  const [name, setName] = useState(defaultPrefix);
  const [country, setCountry] = useState("US");
  const [selectedOffer, setSelectedOffer] = useState<OfferItem | null>(null);
  const [domainId, setDomainId] = useState<number | null>(null);
  const [groupId, setGroupId] = useState<number | null>(null);
  const [trafficSourceId, setTrafficSourceId] = useState<number | null>(null);

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [created, setCreated] = useState<CampaignCreateResult | null>(null);

  const loadReferences = async () => {
    setRefsLoading(true);
    setRefsError(null);
    try {
      const data = await api.getReferences();
      setReferences(data);
      setDomainId(data.defaults.domain_id ?? null);
      setGroupId(data.defaults.group_id ?? null);
      setTrafficSourceId(data.defaults.traffic_source_id ?? null);
    } catch (err) {
      setRefsError(err instanceof ApiError ? err.message : "Не удалось загрузить справочники");
    } finally {
      setRefsLoading(false);
    }
  };

  useEffect(() => {
    void loadReferences();
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitError(null);
    setCreated(null);

    if (!name.trim()) {
      setSubmitError("Укажите название кампании");
      return;
    }
    const parsedCountries = country
      .split(",")
      .map((c) => c.trim().toUpperCase())
      .filter(Boolean);
    if (parsedCountries.length === 0 || parsedCountries.some((c) => !/^[A-Z]{2}$/.test(c))) {
      setSubmitError(
        "Укажите один или несколько гео-кодов стран из 2 латинских букв через запятую (например, US, DE, RU)"
      );
      return;
    }
    const uniqueCountries = Array.from(new Set(parsedCountries));
    if (!selectedOffer) {
      setSubmitError("Выберите оффер из списка или введите его ID и нажмите Enter");
      return;
    }

    setSubmitting(true);
    try {
      const result = await api.createCampaign({
        name: name.trim(),
        country: uniqueCountries.join(", "),
        offer_id: selectedOffer.id,
        domain_id: domainId,
        group_id: groupId,
        traffic_source_id: trafficSourceId,
      });
      setCreated(result);
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : "Ошибка при создании кампании");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="stack">
      <div className="card">
        <div className="card__header">
          <div>
            <h2>Создаватор кампаний</h2>
            <p className="muted">
              Создает кампанию с доменом, группой, источником и двумя потоками: выбранное ГЕО {"->"}
              {" "}Google, остальной трафик {"->"} выбранный оффер (100%).
            </p>
          </div>
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            onClick={() => void loadReferences()}
            disabled={refsLoading}
          >
            Обновить справочники
          </button>
        </div>

        {refsError && <div className="alert alert--error">{refsError}</div>}

        <form onSubmit={handleSubmit} className="form-grid">
          <div className="field">
            <label htmlFor="camp-name">Название кампании</label>
            <input
              id="camp-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={`${defaultPrefix}campaign1`}
              required
            />
            <span className="hint">Рекомендуемый префикс: {defaultPrefix}...</span>
          </div>

          <div className="field">
            <label htmlFor="camp-country">Гео-коды стран (ISO alpha-2, через запятую)</label>
            <input
              id="camp-country"
              type="text"
              value={country}
              onChange={(e) => setCountry(e.target.value.toUpperCase())}
              placeholder="US, DE, RU"
              required
            />
            <span className="hint">
              Можно указать несколько стран через запятую. Трафик из них уйдет на
              https://www.google.com
            </span>
          </div>

          <div className="field field--full">
            <label htmlFor="creator-offer-search">Оффер в Keitaro (для второго потока)</label>
            <OfferSearchSelect
              inputId="creator-offer-search"
              value={selectedOffer}
              onChange={setSelectedOffer}
            />
          </div>

          <div className="field">
            <label htmlFor="camp-domain">Домен</label>
            <SearchableSelect
              inputId="camp-domain"
              options={references?.domains ?? []}
              value={domainId}
              onChange={setDomainId}
              emptyOptionLabel="По умолчанию"
              placeholder="Поиск домена..."
              disabled={refsLoading}
            />
          </div>

          <div className="field">
            <label htmlFor="camp-group">Группа кампаний</label>
            <SearchableSelect
              inputId="camp-group"
              options={references?.groups ?? []}
              value={groupId}
              onChange={setGroupId}
              emptyOptionLabel="По умолчанию"
              placeholder="Поиск группы..."
              disabled={refsLoading}
            />
          </div>

          <div className="field">
            <label htmlFor="camp-source">Источник трафика</label>
            <SearchableSelect
              inputId="camp-source"
              options={references?.traffic_sources ?? []}
              value={trafficSourceId}
              onChange={setTrafficSourceId}
              emptyOptionLabel="По умолчанию"
              placeholder="Поиск источника..."
              disabled={refsLoading}
            />
          </div>

          {submitError && <div className="alert alert--error field--full">{submitError}</div>}

          <div className="field--full form-actions">
            <button type="submit" className="btn btn--primary" disabled={submitting}>
              {submitting ? "Создание в Keitaro..." : "Создать кампанию"}
            </button>
          </div>
        </form>
      </div>

      {created && (
        <div className="card card--success">
          <div className="card__header">
            <div>
              <h3>
                Кампания создана: #{created.keitaro_id} - {created.name}
              </h3>
              <p className="muted">
                Alias: {created.alias || "-"} | Домен: {created.domain_id ?? "-"} | Группа:{" "}
                {created.group_id ?? "-"} | Источник: {created.traffic_source_id ?? "-"}
              </p>
            </div>
            <button
              type="button"
              className="btn btn--primary"
              onClick={() => onOpenInEditor(created.keitaro_id)}
            >
              Открыть в редакторе
            </button>
          </div>

          <div className="created-streams">
            {created.streams.map((st) => (
              <div key={st.id} className="created-stream-item">
                <strong>
                  Поток #{st.position}: {st.name}
                </strong>{" "}
                <span className="muted">(Keitaro ID: {st.keitaro_id}, схема: {st.schema_name})</span>
                {st.has_offers ? (
                  <div className="muted">
                    Офферы:{" "}
                    {st.offers
                      .map((o) => `#${o.offer_keitaro_id} ${o.offer_name} (${o.draft_share}%)`)
                      .join(", ")}
                  </div>
                ) : (
                  <div className="muted">Редирект на https://www.google.com</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
