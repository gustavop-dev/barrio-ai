// Tu turno additions of rev 18 that only the Tu turno view uses.
import { api } from './client';

/** Marks cards as seen (Nueva → Vista). They keep counting: only the «NUEVA» tag goes away. */
export const markTurnoSeen = (ids: string[]) => api.post<{ count: number }>('/api/v1/tu-turno/vistos', { ids });
