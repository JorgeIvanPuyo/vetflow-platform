"use client";

import { Stethoscope } from "lucide-react";
import { useEffect, useState } from "react";

export function ClinicBrandMark({
  logoUrl,
  onLogoError,
}: {
  logoUrl?: string | null;
  onLogoError: () => Promise<void>;
}) {
  const [hasLogoError, setHasLogoError] = useState(false);

  useEffect(() => {
    setHasLogoError(false);
  }, [logoUrl]);

  if (logoUrl && !hasLogoError) {
    return (
      <span className="brand__mark brand__mark--image" aria-hidden="true">
        <img
          alt=""
          src={logoUrl}
          onError={() => {
            setHasLogoError(true);
            void onLogoError();
          }}
        />
      </span>
    );
  }

  return (
    <span className="brand__mark" aria-hidden="true">
      <Stethoscope size={20} />
    </span>
  );
}