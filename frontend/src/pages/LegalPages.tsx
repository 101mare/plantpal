import { Link } from "react-router-dom";
import type { ReactNode } from "react";

function LegalShell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="mx-auto max-w-2xl p-4">
      <header className="mb-6 flex items-center justify-between">
        <h1 className="pp-heading text-lg" tabIndex={-1}>
          {title}
        </h1>
        <Link to="/" className="pp-btn" aria-label="Zurück">
          ←
        </Link>
      </header>
      <div className="pp-frame space-y-3 p-6 text-xs leading-relaxed">{children}</div>
    </div>
  );
}

export function ImpressumPage() {
  return (
    <LegalShell title="Impressum">
      <p>Angaben gemäß § 5 DDG (TMG).</p>
      <p>
        <b>Diensteanbieter:</b>
        <br />
        [Dein Name]
        <br />
        [Straße Nr.]
        <br />
        [PLZ Ort]
      </p>
      <p>
        <b>Kontakt:</b>
        <br />
        E-Mail: [deine@email.de]
      </p>
      <p>
        <b>Verantwortlich für den Inhalt nach § 18 Abs. 2 MStV:</b>
        <br />
        [Dein Name], Anschrift wie oben.
      </p>
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
      <p>
        <b>Cookies:</b> Es werden ausschließlich technisch notwendige Cookies gesetzt (Session +
        CSRF-Schutz). Kein Tracking, keine Analyse, keine Werbung — daher ist kein Cookie-Banner
        erforderlich.
      </p>
      <p>
        <b>Auftragsverarbeiter:</b> Für den E-Mail-Versand (Login-Links/Codes, Erinnerungen) wird
        Resend (resend.com) genutzt. Login-Tokens stehen kurzzeitig in den Versand-Logs (single-use,
        kurze Gültigkeit). Schließe für den Produktivbetrieb einen AVV mit Resend ab.
      </p>
      <p>
        <b>Hosting:</b> Selbst gehostet; der Zugang läuft über Cloudflare Tunnel (Cloudflare
        terminiert TLS und sieht den Klartext-Traffic am Edge).
      </p>
      <p>
        <b>Deine Rechte (DSGVO):</b> Auskunft &amp; Datenübertragbarkeit (Art. 15/20) über „Meine
        Daten exportieren" in den Einstellungen. Löschung (Art. 17) über „Account löschen".
        E-Mail-Adresse änderbar in den Einstellungen.
      </p>
      <p>
        <b>Verantwortlicher:</b> siehe{" "}
        <Link to="/impressum" className="text-pp-gold underline">
          Impressum
        </Link>
        .
      </p>
      <p className="opacity-60">
        Hinweis: Vorlage — bitte an deinen Betrieb anpassen und rechtlich prüfen lassen.
      </p>
    </LegalShell>
  );
}
