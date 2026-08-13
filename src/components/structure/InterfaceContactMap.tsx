import type { InterfaceContact } from '@/types/platform';

interface InterfaceContactMapProps {
  contacts: InterfaceContact[];
}

const typeLabel: Record<InterfaceContact['contactType'], string> = {
  hydrophobic: 'Hydrophobic',
  electrostatic: 'Electrostatic',
  'hydrogen-bond': 'H-bond',
  'van-der-waals': 'vdW',
};

const typeColor: Record<InterfaceContact['contactType'], string> = {
  hydrophobic: 'text-amber-700 bg-amber-50 border-amber-200',
  electrostatic: 'text-blue-700 bg-blue-50 border-blue-200',
  'hydrogen-bond': 'text-emerald-700 bg-emerald-50 border-emerald-200',
  'van-der-waals': 'text-gray-700 bg-gray-50 border-gray-200',
};

export function InterfaceContactMap({ contacts }: InterfaceContactMapProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-xh-border">
            <th className="text-left py-2 px-3 text-xs font-medium text-xh-muted">Epitope Residue</th>
            <th className="text-left py-2 px-3 text-xs font-medium text-xh-muted">Peptide Residue</th>
            <th className="text-left py-2 px-3 text-xs font-medium text-xh-muted">Distance</th>
            <th className="text-left py-2 px-3 text-xs font-medium text-xh-muted">Contact Type</th>
          </tr>
        </thead>
        <tbody>
          {contacts.map((contact, i) => (
            <tr key={i} className="border-b border-gray-50 last:border-0">
              <td className="py-2 px-3 font-mono text-xs text-xh-text">{contact.epitopeResidue}</td>
              <td className="py-2 px-3 font-mono text-xs text-xh-text">{contact.peptideResidue}</td>
              <td className="py-2 px-3 text-xs text-xh-muted">{contact.distance.toFixed(1)} Å</td>
              <td className="py-2 px-3">
                <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium border ${typeColor[contact.contactType]}`}>
                  {typeLabel[contact.contactType]}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
