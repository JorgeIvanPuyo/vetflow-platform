import { ExternalLink, PlayCircle } from "lucide-react";
import { isYouTubeUrl } from "../helpers";

export function HelpVideoLink({ url, label }: { url?: string; label?: string }) {
  if (!url || !isYouTubeUrl(url)) return null;
  return <section className="panel help-video"><h2><PlayCircle aria-hidden="true" size={22} />Ver tutorial en video</h2><a className="secondary-button" href={url} target="_blank" rel="noreferrer">{label ?? "Ver en YouTube"}<ExternalLink aria-hidden="true" size={16} /><span className="sr-only"> (se abre en una nueva pestaña)</span></a></section>;
}
