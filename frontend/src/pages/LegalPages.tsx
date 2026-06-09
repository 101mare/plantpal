import { Link } from "react-router-dom";
import type { ReactNode } from "react";
import { useI18n } from "../i18n";

function LegalShell({ title, children }: { title: string; children: ReactNode }) {
  const { t } = useI18n();
  return (
    <div className="mx-auto max-w-2xl p-4">
      {/* Back lives top-left per iOS HIG; min-w-0 lets the long German title wrap instead of overflow. */}
      <header className="mb-6 flex items-center gap-3">
        <Link to="/" className="pp-btn shrink-0" aria-label={t("nav.back")}>
          ←
        </Link>
        <h1 className="pp-heading min-w-0 text-lg" tabIndex={-1}>
          {title}
        </h1>
      </header>
      <div className="pp-frame space-y-3 p-6 text-sm leading-relaxed">{children}</div>
    </div>
  );
}

export function ImpressumPage() {
  return (
    <LegalShell title="Impressum">
      <p>Angaben gemäß § 5 DDG (TMG).</p>
      <section className="space-y-1">
        <h2 className="text-sm font-bold">Diensteanbieter</h2>
        <p>
          [Dein Name]
          <br />
          [Straße Nr.]
          <br />
          [PLZ Ort]
        </p>
      </section>
      <section className="space-y-1">
        <h2 className="text-sm font-bold">Kontakt</h2>
        <p>E-Mail: [deine@email.de]</p>
      </section>
      <section className="space-y-1">
        <h2 className="text-sm font-bold">Verantwortlich für den Inhalt nach § 18 Abs. 2 MStV</h2>
        <p>[Dein Name], Anschrift wie oben.</p>
      </section>
      <p className="opacity-60">
        Hinweis: Vorlage — bitte mit deinen Daten füllen und rechtlich prüfen lassen. Diese App gibt
        keine Rechtsberatung.
      </p>
    </LegalShell>
  );
}

export function DatenschutzPage() {
  return (
    <LegalShell title="Datenschutzerklärung">
      <p>
        PlantPal speichert nur die zur Funktion nötigen Daten: deine E-Mail-Adresse, deine Pflanzen
        (inkl. Fotos, Notizen, Standort) und deine Gieß-Historie.
      </p>
      <section className="space-y-1">
        <h2 className="text-sm font-bold">Cookies</h2>
        <p>
          Es werden ausschließlich technisch notwendige Cookies gesetzt (Session + CSRF-Schutz).
          Kein Tracking, keine Analyse, keine Werbung — daher ist kein Cookie-Banner erforderlich.
        </p>
      </section>
      <section className="space-y-1">
        <h2 className="text-sm font-bold">Auftragsverarbeiter</h2>
        <p>
          Für den E-Mail-Versand (Login-Links/Codes, Erinnerungen) wird Resend (resend.com) genutzt.
          Login-Tokens stehen kurzzeitig in den Versand-Logs (single-use, kurze Gültigkeit).
          Schließe für den Produktivbetrieb einen AVV mit Resend ab.
        </p>
      </section>
      <section className="space-y-1">
        <h2 className="text-sm font-bold">Hosting</h2>
        <p>
          Selbst gehostet; der Zugang läuft über Cloudflare Tunnel (Cloudflare terminiert TLS und
          sieht den Klartext-Traffic am Edge).
        </p>
      </section>
      <section className="space-y-1">
        <h2 className="text-sm font-bold">Deine Rechte (DSGVO)</h2>
        <p>
          Auskunft &amp; Datenübertragbarkeit (Art. 15/20) über „Meine Daten exportieren" in den
          Einstellungen. Löschung (Art. 17) über „Account löschen". E-Mail-Adresse änderbar in den
          Einstellungen.
        </p>
      </section>
      <section className="space-y-1">
        <h2 className="text-sm font-bold">Verantwortlicher</h2>
        <p>
          siehe{" "}
          <Link to="/impressum" className="text-pp-gold underline">
            Impressum
          </Link>
          .
        </p>
      </section>
      <p className="opacity-60">
        Hinweis: Vorlage — bitte an deinen Betrieb anpassen und rechtlich prüfen lassen.
      </p>
    </LegalShell>
  );
}
