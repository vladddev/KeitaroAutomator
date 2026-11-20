import { useEffect, useState } from "react";
import { api, setUnauthorizedHandler } from "./api/client";
import { CampaignCreator } from "./components/CampaignCreator";
import { CampaignEditor } from "./components/CampaignEditor";
import { LoginPage } from "./components/LoginPage";
import type { AuthMe } from "./types";

type Tab = "creator" | "editor";

export function App() {
  const [auth, setAuth] = useState<AuthMe | null>(null);
  const [loadingAuth, setLoadingAuth] = useState(true);
  const [activeTab, setActiveTab] = useState<Tab>("creator");
  const [editorCampaignId, setEditorCampaignId] = useState<number | null>(null);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setAuth((prev) =>
        prev
          ? { ...prev, authenticated: false, mode: null, key_hint: null }
          : {
              authenticated: false,
              mode: null,
              key_hint: null,
              default_key_configured: false,
              default_campaign_prefix: "test_lukashov_",
            }
      );
    });
    return () => setUnauthorizedHandler(null);
  }, []);

  useEffect(() => {
    const init = async () => {
      try {
        const me = await api.getMe();
        setAuth(me);
      } catch {
        setAuth({
          authenticated: false,
          mode: null,
          key_hint: null,
          default_key_configured: false,
          default_campaign_prefix: "test_lukashov_",
        });
      } finally {
        setLoadingAuth(false);
      }
    };
    void init();
  }, []);

  const handleLogout = async () => {
    try {
      await api.logout();
    } finally {
      setAuth((prev) =>
        prev
          ? { ...prev, authenticated: false, mode: null, key_hint: null }
          : null
      );
    }
  };

  if (loadingAuth || !auth) {
    return (
      <div className="auth-shell">
        <div className="card auth-card">Загрузка...</div>
      </div>
    );
  }

  if (!auth.authenticated) {
    return (
      <LoginPage
        defaultKeyConfigured={auth.default_key_configured}
        onSuccess={(nextAuth) => setAuth(nextAuth)}
      />
    );
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar__inner">
          <div className="topbar__brand">
            <strong>Keitaro API Wrapper</strong>
            <nav className="tabs">
              <button
                type="button"
                className={`tab ${activeTab === "creator" ? "tab--active" : ""}`}
                onClick={() => setActiveTab("creator")}
              >
                Создаватор
              </button>
              <button
                type="button"
                className={`tab ${activeTab === "editor" ? "tab--active" : ""}`}
                onClick={() => setActiveTab("editor")}
              >
                Редактор
              </button>
            </nav>
          </div>

          <div className="topbar__user">
            <span className="badge badge--neutral">{auth.key_hint || "Авторизован"}</span>
            <button type="button" className="btn btn--ghost btn--sm" onClick={() => void handleLogout()}>
              Выйти
            </button>
          </div>
        </div>
      </header>

      <main className="container">
        {activeTab === "creator" ? (
          <CampaignCreator
            defaultPrefix={auth.default_campaign_prefix}
            onOpenInEditor={(campaignKeitaroId) => {
              setEditorCampaignId(campaignKeitaroId);
              setActiveTab("editor");
            }}
          />
        ) : (
          <CampaignEditor initialCampaignId={editorCampaignId} />
        )}
      </main>
    </div>
  );
}
