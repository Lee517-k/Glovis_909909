// Trimmed from the reference project's pages/scenario/helpers.ts to just
// colorFor — radarValuesFor/transferCount/tagLabel/tagTone operate on the
// types/proposal.ts Proposal shape, which belonged to the reference's
// System A (CoordinatorPanel/ProposalCard/ResultsSection), never wired to
// ScenarioPage/SavedPage and not ported here.

export const PALETTE = ["#7A5AF8", "#12A47B", "#1E6FBF", "#E08A00", "#D8443C", "#4E32B5", "#0E9E62", "#3D8AE0"];

export function colorFor(index: number): string {
  return PALETTE[index % PALETTE.length];
}
