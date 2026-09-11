"use client";

import Image from "next/image";
import Link from "next/link";
import { useState } from "react";
import type { HelpStep as HelpStepContent } from "../types";

export function HelpStep({ step }: { step: HelpStepContent }) {
  const [failedSource, setFailedSource] = useState<string>();
  return (
    <li className="help-step">
      <h3>{step.title}</h3>
      <p>{step.description}</p>
      {step.appRoute ? <Link className="inline-link" href={step.appRoute}>{step.appRouteLabel ?? "Abrir en Vetflow"}</Link> : null}
      {step.imageSrc && step.imageSrc !== failedSource ? <figure className="help-screenshot"><Image src={step.imageSrc} alt={step.imageAlt} width={1200} height={800} unoptimized onError={() => setFailedSource(step.imageSrc)} /></figure> : null}
    </li>
  );
}
