import { FormEvent, useState } from "react";
import { ApiError, api } from "../api/client";
import type { AuthMe } from "../types";

interface LoginPageProps {
  defaultKeyConfigured: boolean;
  onSuccess: (auth: AuthMe) => void;
}

export function LoginPage({ defaultKeyConfigured, onSuccess }: LoginPageProps) {
  const [apiKey, setApiKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const auth = await api.login(apiKey);
      onSuccess(auth);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось выполнить вход");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-shell">
      <div className="card auth-card">
        <h1>Keitaro API Wrapper</h1>
        <p className="muted">
          Вход в панель управления кампаниями и потоками Keitaro.
        </p>

        {!defaultKeyConfigured && (
          <div className="alert alert--warning">
            Тестовый API ключ не задан в конфигурации сервера (.env). Введите свой ключ Keitaro
            вручную.
          </div>
        )}

        <form onSubmit={handleSubmit} className="stack">
          <div className="field">
            <label htmlFor="api-key-input">API ключ Keitaro (необязательно)</label>
            <div className="input-row">
              <input
                id="api-key-input"
                type={showKey ? "text" : "password"}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="Оставьте пустым для входа с тестовым ключом"
                autoComplete="off"
              />
              <button
                type="button"
                className="btn btn--ghost"
                onClick={() => setShowKey((prev) => !prev)}
              >
                {showKey ? "Скрыть" : "Показать"}
              </button>
            </div>
            <span className="hint">
              Если оставить поле пустым, будет использован единый тестовый ключ из настроек
              сервера.
            </span>
          </div>

          {error && <div className="alert alert--error">{error}</div>}

          <button type="submit" className="btn btn--primary" disabled={loading}>
            {loading
              ? "Проверка ключа..."
              : apiKey.trim()
                ? "Войти со своим ключом"
                : "Войти с тестовым ключом"}
          </button>
        </form>
      </div>
    </div>
  );
}
