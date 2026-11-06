import { env } from 'cloudflare:workers';
import { handleOffice } from '../../../../lib/office-relay.mjs';
export const dynamic = 'force-dynamic';
export async function GET(request: Request) { return handleOffice(request,env); }
export async function POST(request: Request) { return handleOffice(request,env); }
