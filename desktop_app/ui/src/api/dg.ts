import { invoke } from '@tauri-apps/api/core'

export type EncryptReq = {
  path: string
  recipients: string[]
  labels?: string[]
  outDir?: string
}

export type DecryptReq = {
  path: string
  outDir?: string
}

export async function encryptFile(req: EncryptReq): Promise<string> {
  return invoke<string>('encrypt_file', {
    path: req.path,
    recipients: req.recipients,
    labels: req.labels,
    out_dir: req.outDir,
  })
}

export async function decryptFile(req: DecryptReq): Promise<string> {
  return invoke<string>('decrypt_file', {
    path: req.path,
    out_dir: req.outDir,
  })
}
