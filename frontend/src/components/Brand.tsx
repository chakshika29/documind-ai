import { Layers3 } from 'lucide-react';
import { Link } from 'react-router-dom';

export function Brand() {
  return <Link className="brand" to="/"><span><Layers3 size={21} aria-hidden="true" /></span>DocuMind <b>AI</b></Link>;
}
