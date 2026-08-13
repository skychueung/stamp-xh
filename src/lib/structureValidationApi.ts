import type {
  StructureValidationData,
  InterfaceContact,
} from '@/types/platform';

/**
 * Structure Validation API 返回的完整结果。
 * 当前为 mock 实现，后续替换为真实后端调用。
 */
export interface StructureValidationResult {
  candidateId: string;
  complexPdbUrl: string;
  targetChainId: string;
  peptideChainId: string;
  epitopeResidueRange: {
    start: number;
    end: number;
  };
  ipTM: number;
  pDockQ: number;
  interfaceDeltaG: number;
  epitopeContactRatio: number;
  offEpitopeBindingRisk: 'low' | 'medium' | 'high';
  contactResidues: InterfaceContact[];
  bindingSiteMatch: 'passed' | 'warning' | 'failed';
  validationStatus: 'pass' | 'warning' | 'fail';
  alphaFoldStatus: 'completed' | 'running' | 'pending';
  flexPepDockStatus: 'completed' | 'running' | 'pending';
  foldXEnergy: number;
}

/**
 * 获取指定候选肽的结构验证结果。
 *
 * @param candidateId - 候选肽唯一标识
 * @returns Promise<StructureValidationResult>
 *
 * @example
 * ```ts
 * const result = await fetchStructureValidationResult('candidate-001');
 * console.log(result.epitopeContactRatio); // 0.91
 * ```
 */
export async function fetchStructureValidationResult(
  candidateId: string
): Promise<StructureValidationResult> {
  // TODO: 后端就绪后替换为真实 API 调用
  // const response = await fetch(`/api/structure-validation/${candidateId}`);
  // if (!response.ok) throw new Error(`HTTP ${response.status}`);
  // return response.json();

  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({
        candidateId,
        complexPdbUrl: '/structures/mock_complex.pdb',
        targetChainId: 'A',
        peptideChainId: 'B',
        epitopeResidueRange: { start: 455, end: 465 },
        ipTM: 0.87,
        pDockQ: 0.78,
        interfaceDeltaG: -12.4,
        epitopeContactRatio: 0.91,
        offEpitopeBindingRisk: 'low',
        contactResidues: [
          { epitopeResidue: 'Y453', peptideResidue: 'W3', distance: 3.2, contactType: 'hydrophobic' },
          { epitopeResidue: 'R454', peptideResidue: 'D5', distance: 2.8, contactType: 'electrostatic' },
          { epitopeResidue: 'G496', peptideResidue: 'Y4', distance: 3.5, contactType: 'van-der-waals' },
          { epitopeResidue: 'Y505', peptideResidue: 'K6', distance: 3.0, contactType: 'hydrogen-bond' },
          { epitopeResidue: 'N487', peptideResidue: 'K2', distance: 3.4, contactType: 'hydrogen-bond' },
          { epitopeResidue: 'F486', peptideResidue: 'W1', distance: 3.6, contactType: 'hydrophobic' },
          { epitopeResidue: 'Q493', peptideResidue: 'R7', distance: 3.1, contactType: 'electrostatic' },
          { epitopeResidue: 'Y489', peptideResidue: 'K9', distance: 2.9, contactType: 'hydrogen-bond' },
        ],
        bindingSiteMatch: 'passed',
        validationStatus: 'pass',
        alphaFoldStatus: 'completed',
        flexPepDockStatus: 'completed',
        foldXEnergy: -12.4,
      });
    }, 800);
  });
}

/**
 * 批量获取多个候选肽的结构验证结果。
 *
 * @param candidateIds - 候选肽 ID 数组
 * @returns Promise<StructureValidationResult[]>
 */
export async function fetchBatchStructureValidation(
  candidateIds: string[]
): Promise<StructureValidationResult[]> {
  const results = await Promise.all(
    candidateIds.map((id) => fetchStructureValidationResult(id))
  );
  return results;
}

/**
 * 将后端原始数据转换为前端 StructureValidationData 格式。
 * 用于 API 响应适配层。
 */
export function adaptToStructureValidationData(
  result: StructureValidationResult
): StructureValidationData {
  return {
    complexPdbUrl: result.complexPdbUrl,
    targetChainId: result.targetChainId,
    peptideChainId: result.peptideChainId,
    epitopeResidueRange: result.epitopeResidueRange,
    contactResidues: result.contactResidues.map((c) => ({
      targetResidue: c.epitopeResidue,
      peptideResidue: c.peptideResidue,
      distance: c.distance,
      type: c.contactType,
    })),
    interfaceMetrics: {
      ipTM: result.ipTM,
      pDockQ: result.pDockQ,
      interfaceDeltaG: result.interfaceDeltaG,
      epitopeContactRatio: result.epitopeContactRatio,
      contactingResidues: result.contactResidues.length,
      distanceToEpitope: 2.8,
    },
    offEpitopeBindingRisk: result.offEpitopeBindingRisk,
    bindingSiteMatch: result.bindingSiteMatch,
    alphaFoldStatus: result.alphaFoldStatus,
    flexPepDockStatus: result.flexPepDockStatus,
    foldXEnergy: result.foldXEnergy,
    modelSource: 'AlphaFold-Multimer',
    confidence: result.epitopeContactRatio >= 0.75 ? 'high' : 'medium',
  };
}
