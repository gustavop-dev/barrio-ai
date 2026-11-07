import { SesionBlock } from '@/ajustes/SesionBlock';
import { Placeholder } from '@/components/shell/Placeholder';

/** Ajustes: the full view comes in the next phase; the session, devices and pushes are here already. */
export default function AjustesScreen() {
  return (
    <Placeholder testID="screen-ajustes" title="Ajustes" subtitle="La máquina, la autonomía, el gasto y tu sesión.">
      <SesionBlock />
    </Placeholder>
  );
}
