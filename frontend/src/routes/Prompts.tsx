import { useCallback, useEffect, useState } from "react";
import { getPrompt, listPacks, savePrompt } from "../api/client";
import type { Pack, PromptDetail } from "../api/types";
import { useLocale } from "../i18n";

export function Prompts() {
  const { t } = useLocale();
  const [packs, setPacks] = useState<Pack[]>([]);
  const [activePack, setActivePack] = useState<string | null>(null);
  const [activeVersion, setActiveVersion] = useState<string | null>(null);
  const [detail, setDetail] = useState<PromptDetail | null>(null);
  const [draft, setDraft] = useState<string>("");
  const [newVersion, setNewVersion] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const reloadPacks = useCallback(async () => {
    try {
      const data = await listPacks();
      setPacks(data);
      if (!activePack && data[0]) {
        setActivePack(data[0].name);
        setActiveVersion(data[0].versions.at(-1)?.version ?? null);
      }
    } catch (err) {
      setError(String(err));
    }
  }, [activePack]);

  useEffect(() => {
    reloadPacks();
  }, [reloadPacks]);

  useEffect(() => {
    if (!activePack || !activeVersion) return;
    let cancelled = false;
    getPrompt(activePack, activeVersion)
      .then((d) => {
        if (cancelled) return;
        setDetail(d);
        setDraft(d.template_raw);
        setNewVersion(bumpVersion(d.version));
        setError(null);
        setNotice(null);
      })
      .catch((err) => setError(String(err)));
    return () => {
      cancelled = true;
    };
  }, [activePack, activeVersion]);

  const activePackDef = packs.find((p) => p.name === activePack);

  const save = async () => {
    if (!activePack || !newVersion) return;
    setError(null);
    setNotice(null);
    try {
      // Rewrite the frontmatter version field to match the new version so the
      // renderer's validator accepts the file.
      const rewritten = draft.replace(
        /^(\s*version\s*:\s*)[^\n]+/m,
        `$1${newVersion}`,
      );
      await savePrompt(activePack, newVersion, rewritten);
      setNotice(`${t("routes.prompts.savedPrefix")} ${activePack}/${newVersion}`);
      await reloadPacks();
      setActiveVersion(newVersion);
    } catch (err) {
      setError(String(err));
    }
  };

  return (
    <div className="flex gap-4 max-w-[1400px] mx-auto">
      <aside className="w-[260px] shrink-0 rounded-lg bg-stone-900 ring-1 ring-white/5 p-3">
        <h2 className="text-sm font-semibold mb-2">{t("routes.prompts.packsHeader")}</h2>
        {packs.length === 0 && (
          <p className="text-xs text-stone-500">{t("routes.prompts.packsEmpty")}</p>
        )}
        <ul className="space-y-3">
          {packs.map((p) => (
            <li key={p.name}>
              <div
                className={`font-medium text-sm cursor-pointer ${
                  activePack === p.name ? "text-amber-300" : "text-stone-200"
                }`}
                onClick={() => {
                  setActivePack(p.name);
                  setActiveVersion(p.versions.at(-1)?.version ?? null);
                }}
              >
                {p.name}
              </div>
              <ul className="ml-2 mt-1 space-y-0.5">
                {p.versions.map((v) => (
                  <li key={v.version}>
                    <button
                      data-testid={`prompt-version-${p.name}-${v.version}`}
                      onClick={() => {
                        setActivePack(p.name);
                        setActiveVersion(v.version);
                      }}
                      className={`w-full text-left text-xs px-2 py-0.5 rounded ${
                        activePack === p.name && activeVersion === v.version
                          ? "bg-stone-800 text-amber-300"
                          : "text-stone-400 hover:bg-stone-800/60"
                      }`}
                      title={v.description ?? ""}
                    >
                      {v.version}
                      {v.description && (
                        <span className="ml-2 opacity-60 truncate inline-block max-w-[150px] align-middle">
                          {v.description}
                        </span>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      </aside>

      <section className="flex-1 min-w-0 flex flex-col gap-3">
        <div className="flex items-baseline gap-3">
          <h1 className="text-xl font-semibold">
            {activePack ? `${activePack} / ${activeVersion ?? ""}` : t("routes.prompts.defaultTitle")}
          </h1>
          {detail && (
            <span className="text-xs text-stone-500 font-mono">
              {t("routes.prompts.hashPrefix")} {detail.template_hash.slice(0, 12)}…
            </span>
          )}
          {activePackDef && (
            <span className="text-xs text-stone-500 ml-auto">
              {activePackDef.versions.length}{" "}
              {activePackDef.versions.length === 1
                ? t("routes.prompts.versionSingular")
                : t("routes.prompts.versionPlural")}
            </span>
          )}
        </div>
        {detail?.description && (
          <p className="text-sm text-stone-400">{detail.description}</p>
        )}
        {detail && (
          <div className="text-xs text-stone-500">
            {t("routes.prompts.declaredVariables")}{" "}
            <span className="text-stone-300">{detail.declared_variables.join(", ")}</span>
          </div>
        )}
        {error && (
          <div className="rounded bg-red-900/30 text-red-200 p-2 text-sm ring-1 ring-red-500/30">
            {error}
          </div>
        )}
        {notice && (
          <div className="rounded bg-emerald-900/30 text-emerald-200 p-2 text-sm ring-1 ring-emerald-500/30">
            {notice}
          </div>
        )}
        <textarea
          data-testid="prompt-editor"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          spellCheck={false}
          className="w-full min-h-[520px] font-mono text-[12px] bg-black/40 text-stone-200 rounded-lg p-3 ring-1 ring-white/10 focus:ring-amber-400 outline-none"
        />
        <div className="flex items-center gap-3 flex-wrap">
          <label className="flex flex-col text-[10px] uppercase tracking-wider opacity-70 gap-0.5">
            <span>{t("routes.prompts.saveAsNewVersion")}</span>
            <input
              value={newVersion}
              onChange={(e) => setNewVersion(e.target.value)}
              placeholder="v2"
              className="normal-case text-sm w-32 bg-stone-900 rounded px-2 py-1 ring-1 ring-white/10 focus:ring-amber-400 outline-none"
            />
          </label>
          <button
            data-testid="prompt-save"
            onClick={save}
            disabled={!activePack || !newVersion}
            className="px-4 py-2 rounded-lg font-semibold bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 transition"
          >
            {t("routes.prompts.save")}
          </button>
          <p className="text-xs text-stone-500">
            {t("routes.prompts.diskNotePrefix")} <code>git</code>.
          </p>
        </div>
      </section>
    </div>
  );
}

function bumpVersion(current: string): string {
  const m = current.match(/^v(\d+)$/);
  if (!m) return `${current}_next`;
  return `v${parseInt(m[1], 10) + 1}`;
}
