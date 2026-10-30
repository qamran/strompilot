"use client";

/** Über view: product story, pipeline, trust, models, sources. */

import { useLang } from "../../lib/i18n";

const MODELS: { name: string; roleKey: "roleSpark" | "roleOpen" | "roleWonder" | "roleSam" | "roleImage" }[] = [
  { name: "Muse Spark 1.3 (Meta)", roleKey: "roleSpark" },
  { name: "Muse Spark Open (Baseten)", roleKey: "roleOpen" },
  { name: "Muse Wonder (Meta)", roleKey: "roleWonder" },
  { name: "SAM 3.1 (Meta)", roleKey: "roleSam" },
  { name: "Muse Image (Meta)", roleKey: "roleImage" },
];

export default function AboutPage() {
  const { t } = useLang();
  const steps = [
    { title: t.step1Title, body: t.step1Body },
    { title: t.step2Title, body: t.step2Body },
    { title: t.step3Title, body: t.step3Body },
  ];
  const pipeline = [
    { name: t.pipe1Name, body: t.pipe1Body },
    { name: t.pipe2Name, body: t.pipe2Body },
    { name: t.pipe3Name, body: t.pipe3Body },
    { name: t.pipe4Name, body: t.pipe4Body },
    { name: t.pipe5Name, body: t.pipe5Body },
    { name: t.pipe6Name, body: t.pipe6Body },
  ];
  const trust = [t.trustLocal, t.trustPhotos, t.trustPii, t.trustGlass];
  return (
    <>
      <section className="panel">
        <h2>{t.aboutTitle}</h2>
        <p className="lede">{t.tagline}</p>
        <p>{t.aboutIntro}</p>
        <ol className="steps">
          {steps.map((step) => (
            <li key={step.title}>
              <strong>{step.title}</strong>
              <span>{step.body}</span>
            </li>
          ))}
        </ol>
      </section>
      <section className="panel">
        <h2>{t.pipeTitle}</h2>
        <ol className="pipeline">
          {pipeline.map((stage) => (
            <li key={stage.name}>
              <strong>{stage.name}</strong>
              <span>{stage.body}</span>
            </li>
          ))}
        </ol>
      </section>
      <section className="panel">
        <h2>{t.trustTitle}</h2>
        <ul className="checks">
          {trust.map((point) => (
            <li key={point}>{point}</li>
          ))}
        </ul>
      </section>
      <section className="panel">
        <h2>{t.modelsTitle}</h2>
        <dl className="model-rows">
          {MODELS.map((model) => (
            <div key={model.name}>
              <dt>{model.name}</dt>
              <dd>{t[model.roleKey]}</dd>
            </div>
          ))}
        </dl>
      </section>
      <section className="panel">
        <h2>{t.source}</h2>
        <p>
          {t.smardCredit} · {t.awattarCredit} · {t.bdewCredit}
        </p>
      </section>
    </>
  );
}
