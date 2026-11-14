import type { components } from "./schema";
type S = components["schemas"];
export type TemplateInfo = S["TemplateInfo"];
export type TemplateId = TemplateInfo["id"];
export type GeneratorInfo = S["GeneratorInfo"];
export type GeneratorType = GeneratorInfo["id"];
export type CreateAuditRequest = Required<
  Omit<S["CreateAuditRequest"], "generator">
> & { generator: Required<S["GeneratorSpec"]> };
export type CreateAuditResponse = S["CreateAuditResponse"];
export type OHLCRow = S["OHLCRow"];
export type PriceResponse = S["PriceResponse"];
export type Health = S["Health"];
export type Preset = S["Preset"];
export type Progress = S["Progress"];
export type Stage = Progress["stage"];
export type AuditDetail = S["AuditDetail"];
export type AuditListItem = S["AuditListItem"];
export type AuditList = S["AuditList"];
export type FieldError = S["FieldError"];
export type FanChart = S["FanChart"];
export type FanPaths = S["FanPaths"];
export type SharpeChart = S["SharpeChart"];
export type PBOChart = S["PBOChart"];
export type DSRChart = S["DSRChart"];
export type SurvivalChart = S["SurvivalChart"];
export type RealismReport = S["RealismReport"];
export type PriceChart = S["PriceChart"];
