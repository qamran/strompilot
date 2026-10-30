"use client";

/** German/English strings for the Leitstand. */

import { createContext, useContext, useState, type ReactNode } from "react";

export type Lang = "de" | "en";

const STRINGS = {
  de: {
    tagline: "Dein Stromlotse für dynamische Tarife",
    navPrices: "Preise",
    navSchedule: "Fahrplan",
    navMeter: "Zähler",
    navAlarms: "Alarme",
    navAbout: "Über",
    planPlaceholder:
      "Nachtschicht, Baby schläft ab 20 Uhr, Auto muss um 6 voll sein …",
    planButton: "Plan machen",
    planHint: "Ein Satz Alltag wird ein erklärter Tagesplan.",
    today: "Heute",
    avg: "Durchschnitt",
    savingsMonth: "Ersparnis ca.",
    perMonth: "/Mo",
    wallbox: "Wallbox",
    charging: "lädt",
    idle: "bereit",
    unplugged: "nicht angesteckt",
    approve: "Freigeben",
    reject: "Ablehnen",
    memoryTitle: "Gedächtnis",
    memoryEmpty: "Noch keine Erinnerungen.",
    forget: "Vergessen",
    whyTitle: "Warum dieser Block?",
    close: "Schließen",
    formula: "Formel",
    source: "Quelle",
    estimateLabel: "Schätzung auf Standardprofil-Basis",
    quarterHourNote:
      "Unser Feed ist stündlich, dynamische Tarife rechnen viertelstundlich ab.",
    worstHour: "Teuerste Stunde",
    consentTitle: "Einwilligung",
    consentPhoto:
      "Ich stimme zu, dass mein Zählerfoto zur Ablesung an die KI-Modelle (Meta, Baseten) gesendet wird. Das Foto wird nicht gespeichert.",
    consentPlan:
      "Ich stimme zu, dass mein Text zur Planerstellung an die KI-Modelle (Meta, Baseten) gesendet wird. Persönliche Daten werden vorher entfernt.",
    keepPhoto: "Foto für meine Unterlagen speichern (optional)",
    upload: "Foto hochladen",
    confirm: "Bestätigen",
    correctedValue: "Korrigierter Stand (kWh, optional)",
    alertsTitle: "Flex-Alarme",
    watchNow: "Jetzt prüfen",
    noAlerts: "Keine Alarme. Alles ruhig.",
    feedbackTitle: "War der Plan gut?",
    feedbackYes: "Daumen hoch",
    feedbackNo: "Daumen runter",
    feedbackEarly: "Zu früh",
    feedbackLate: "Zu spät",
    feedbackGood: "Genau richtig",
    feedbackThanks: "Danke! Der nächste Plan lernt daraus.",
    reportTitle: "Monatsbericht",
    reportSavings: "Ersparnis gegen Flat",
    reportArt: "Titelbild erzeugen",
    reportArtCached: "Titelbild (gespeichert)",
    traceTitle: "Agenten-Protokoll live",
    scheduleEmpty: "Noch kein Plan. Beschreibe deinen Tag oben.",
    pausedNote: "Der Plan wartet auf deine Freigabe.",
    publishedNote: "Der Plan ist freigegeben.",
    blockedNote: "Der Plan ist blockiert.",
    runningNote: "Der Planer arbeitet …",
    disclaimerFooter:
      "Unverbindliche Orientierung, keine Rechts-, Steuer- oder Anlageberatung.",
    aboutTitle: "Über Strompilot",
    sampleBadge: "Beispieldaten",
    liveBadge: "Live",
    cachedBadge: "Zwischengespeichert",
    smardCredit: "Bundesnetzagentur | SMARD.de (CC BY 4.0)",
    awattarCredit: "aWATTar",
    bdewCredit: "BDEW Lastprofile 2025",
    privacyTitle: "Privates bleibt privat",
    privacyBody:
      "Haushaltsdaten liegen in lokalem SQLite. Fotos werden nur im Speicher verarbeitet und nie gespeichert, außer du stimmst zu. Persönliche Daten werden vor jedem Modellaufruf entfernt. „Vergessen“ löscht Erinnerungen sofort.",
    modelsTitle: "Welche Modelle arbeiten?",
    modelsBody:
      "Muse Spark 1.3 (Meta) denkt nach, Muse Spark Open (Baseten) schreibt Masse, Muse Wonder prüft kritisch, SAM 3.1 findet den Zähler im Foto, Muse Image malt das Titelbild.",
    language: "Sprache",
  },
  en: {
    tagline: "Your power copilot for dynamic tariffs",
    navPrices: "Prices",
    navSchedule: "Plan",
    navMeter: "Meter",
    navAlarms: "Alarms",
    navAbout: "About",
    planPlaceholder:
      "Night shift, baby sleeps from 8pm, car must be full by 6am …",
    planButton: "Make a plan",
    planHint: "One sentence of daily life becomes an explained day plan.",
    today: "Today",
    avg: "Average",
    savingsMonth: "Savings approx.",
    perMonth: "/mo",
    wallbox: "Wallbox",
    charging: "charging",
    idle: "ready",
    unplugged: "unplugged",
    approve: "Approve",
    reject: "Reject",
    memoryTitle: "Memory",
    memoryEmpty: "No memories yet.",
    forget: "Forget",
    whyTitle: "Why this block?",
    close: "Close",
    formula: "Formula",
    source: "Source",
    estimateLabel: "Estimate on standard-profile basis",
    quarterHourNote:
      "Our feed is hourly while dynamic tariffs settle quarter-hourly.",
    worstHour: "Most expensive hour",
    consentTitle: "Consent",
    consentPhoto:
      "I agree that my meter photo is sent to the AI models (Meta, Baseten) for reading. The photo is not stored.",
    consentPlan:
      "I agree that my text is sent to the AI models (Meta, Baseten) for planning. Personal data is removed first.",
    keepPhoto: "Store the photo for my records (optional)",
    upload: "Upload photo",
    confirm: "Confirm",
    correctedValue: "Corrected reading (kWh, optional)",
    alertsTitle: "Flex alarms",
    watchNow: "Check now",
    noAlerts: "No alarms. All quiet.",
    feedbackTitle: "Was the plan good?",
    feedbackYes: "Thumbs up",
    feedbackNo: "Thumbs down",
    feedbackEarly: "Too early",
    feedbackLate: "Too late",
    feedbackGood: "Just right",
    feedbackThanks: "Thanks! The next plan learns from this.",
    reportTitle: "Monthly report",
    reportSavings: "Savings vs flat rate",
    reportArt: "Generate cover art",
    reportArtCached: "Cover art (cached)",
    traceTitle: "Live agent trace",
    scheduleEmpty: "No plan yet. Describe your day above.",
    pausedNote: "The plan waits for your approval.",
    publishedNote: "The plan is approved.",
    blockedNote: "The plan is blocked.",
    runningNote: "The planner is working …",
    disclaimerFooter:
      "Non-binding orientation, not legal, tax, or investment advice.",
    aboutTitle: "About Strompilot",
    sampleBadge: "Sample data",
    liveBadge: "Live",
    cachedBadge: "Cached",
    smardCredit: "Bundesnetzagentur | SMARD.de (CC BY 4.0)",
    awattarCredit: "aWATTar",
    bdewCredit: "BDEW load profiles 2025",
    privacyTitle: "Private stays private",
    privacyBody:
      "Household data stays in local SQLite. Photos are processed in memory only and never stored unless you agree. Personal data is stripped before every model call. “Forget” deletes memories immediately.",
    modelsTitle: "Which models do the work?",
    modelsBody:
      "Muse Spark 1.3 (Meta) reasons, Muse Spark Open (Baseten) writes volume, Muse Wonder reviews critically, SAM 3.1 finds the meter in the photo, Muse Image paints the cover art.",
    language: "Language",
  },
};

export type Strings = (typeof STRINGS)["de"];

interface LangContext {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: Strings;
}

const Context = createContext<LangContext>({
  lang: "de",
  setLang: () => {},
  t: STRINGS.de,
});

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>("de");
  return (
    <Context.Provider value={{ lang, setLang, t: STRINGS[lang] }}>
      {children}
    </Context.Provider>
  );
}

export function useLang(): LangContext {
  return useContext(Context);
}
