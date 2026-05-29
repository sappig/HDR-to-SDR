import { useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Container,
  Divider,
  Grid2,
  List,
  ListItem,
  ListItemText,
  Paper,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
} from '@mui/material'

interface Folder { id: number; path: string; enabled: boolean; created_at: string }
interface FileRecord { id: number; path: string; hdr_detected: boolean; hdr_type: string | null; status: string; resolution: string | null; codec: string | null; bitrate: number | null; audio_tracks: number | null; subtitle_tracks: number | null; file_size: number; scanned_at: string }
interface QueueItem { id: number; media_file_id: number; state: string; progress: number; paused: boolean; sort_order: number; started_at?: string | null; completed_at?: string | null }
interface Settings { max_concurrent_transcodes: number; software_fallback: boolean; output_bitrate: number; output_resolution: string; plex_transcoder_path: string | null; scan_interval: number; log_retention_days: number; qsv_available: boolean; qsv_device: string | null; detected_plex_version: string | null }

const baseUrl = ''

function App() {
  const [folders, setFolders] = useState<Folder[]>([])
  const [files, setFiles] = useState<FileRecord[]>([])
  const [queue, setQueue] = useState<QueueItem[]>([])
  const [settings, setSettings] = useState<Settings | null>(null)
  const [folderPath, setFolderPath] = useState('')
  const [tab, setTab] = useState(0)
  const [message, setMessage] = useState('')
  const [settingsForm, setSettingsForm] = useState<Settings | null>(null)

  const loadAll = async () => {
    const [folderRes, fileRes, queueRes, settingsRes] = await Promise.all([
      fetch(`${baseUrl}/folders`),
      fetch(`${baseUrl}/files`),
      fetch(`${baseUrl}/queue`),
      fetch(`${baseUrl}/settings`),
    ])
    const settingsData = await settingsRes.json()
    setFolders(await folderRes.json())
    setFiles(await fileRes.json())
    setQueue(await queueRes.json())
    setSettings(settingsData)
    setSettingsForm(settingsData)
  }

  useEffect(() => {
    loadAll()
    const interval = setInterval(loadAll, 5000)
    return () => clearInterval(interval)
  }, [])

  const addFolder = async () => {
    const response = await fetch(`${baseUrl}/folders`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: folderPath, enabled: true }),
    })
    if (response.ok) {
      setMessage(`Added ${folderPath}. Restart the container with updated volume mappings.`)
      setFolderPath('')
      await loadAll()
    }
  }

  const removeFolder = async (id: number) => {
    await fetch(`${baseUrl}/folders/${id}`, { method: 'DELETE' })
    await loadAll()
  }

  const toggleFolder = async (id: number) => {
    await fetch(`${baseUrl}/folders/${id}/toggle`, { method: 'POST' })
    await loadAll()
  }

  const pauseQueue = async () => {
    const ids = queue.filter((item) => !item.paused).map((item) => item.id)
    await fetch(`${baseUrl}/queue/pause`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids }),
    })
    await loadAll()
  }

  const resumeQueue = async () => {
    const ids = queue.filter((item) => item.paused).map((item) => item.id)
    await fetch(`${baseUrl}/queue/resume`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids }),
    })
    await loadAll()
  }

  const reorderQueue = async (ids: number[]) => {
    await fetch(`${baseUrl}/queue/reorder`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ order: ids }),
    })
    await loadAll()
  }

  const moveQueueItem = async (itemId: number, direction: 'up' | 'down' | 'top') => {
    const reordered = [...queue]
    const index = reordered.findIndex((item) => item.id === itemId)
    if (index === -1) return
    if (direction === 'up' && index > 0) {
      const [item] = reordered.splice(index, 1)
      reordered.splice(index - 1, 0, item)
    }
    if (direction === 'down' && index < reordered.length - 1) {
      const [item] = reordered.splice(index, 1)
      reordered.splice(index + 1, 0, item)
    }
    if (direction === 'top') {
      const [item] = reordered.splice(index, 1)
      reordered.unshift(item)
    }
    setQueue(reordered)
    await reorderQueue(reordered.map((item) => item.id))
  }

  const removeQueueItem = async (itemId: number) => {
    await fetch(`${baseUrl}/queue/${itemId}`, { method: 'DELETE' })
    await loadAll()
  }

  const completed = queue.filter((item) => item.state === 'Completed').length
  const active = queue.filter((item) => item.state === 'Transcoding').length
  const pending = queue.filter((item) => item.state === 'Pending' || item.state === 'Waiting').length

  const saveSettings = async () => {
    if (!settingsForm) return
    await fetch(`${baseUrl}/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        max_concurrent_transcodes: settingsForm.max_concurrent_transcodes,
        software_fallback: settingsForm.software_fallback,
        output_bitrate: settingsForm.output_bitrate,
        output_resolution: settingsForm.output_resolution,
        plex_transcoder_path: settingsForm.plex_transcoder_path,
        scan_interval: settingsForm.scan_interval,
        log_retention_days: settingsForm.log_retention_days,
      }),
    })
    await loadAll()
  }

  const volumeSnippet = useMemo(() => {
    return folders.map((folder) => `  - ${folder.path}:${folder.path}`).join('\n')
  }, [folders])

  return (
    <Container maxWidth="xl" sx={{ py: 3 }}>
      <Typography variant="h3" gutterBottom>HDR to FHD Transcoding Manager</Typography>
      <Typography variant="body1" color="text.secondary" gutterBottom>
        Monitor HDR media folders, queue SDR/FHD transcoding, and manage hardware-assisted transcoding from one dashboard.
      </Typography>

      {message && <Alert severity="info" sx={{ mb: 2 }}>{message}</Alert>}

      <Grid2 container spacing={2} sx={{ mb: 2 }}>
        <Grid2 size={{ xs: 12, md: 3 }}>
          <Card><CardContent><Typography variant="h6">Monitored Folders</Typography><Typography variant="h4">{folders.length}</Typography></CardContent></Card>
        </Grid2>
        <Grid2 size={{ xs: 12, md: 3 }}>
          <Card><CardContent><Typography variant="h6">HDR Files</Typography><Typography variant="h4">{files.filter((file) => file.hdr_detected).length}</Typography></CardContent></Card>
        </Grid2>
        <Grid2 size={{ xs: 12, md: 3 }}>
          <Card><CardContent><Typography variant="h6">Pending Jobs</Typography><Typography variant="h4">{pending}</Typography></CardContent></Card>
        </Grid2>
        <Grid2 size={{ xs: 12, md: 3 }}>
          <Card><CardContent><Typography variant="h6">QSV</Typography><Typography variant="h4">{settings?.qsv_available ? 'Available' : 'Not Available'}</Typography></CardContent></Card>
        </Grid2>
      </Grid2>

      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="h6" gutterBottom>Folder Management</Typography>
        <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2 }}>
          <TextField fullWidth label="Folder path" value={folderPath} onChange={(e) => setFolderPath(e.target.value)} />
          <Button variant="contained" onClick={addFolder}>Add Folder</Button>
        </Stack>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          The UI shows the required volume mappings below. After adding a folder, restart the container with the updated mapping.
        </Typography>
        <pre style={{ background: '#111', color: '#fff', padding: 12, borderRadius: 8 }}>
{`volumes:
${volumeSnippet || '  # Add folders to generate mappings'}`}
        </pre>
        <List>
          {folders.map((folder) => (
            <ListItem key={folder.id} secondaryAction={
              <Stack direction="row" spacing={1}>
                <Button variant="outlined" onClick={() => toggleFolder(folder.id)}>{folder.enabled ? 'Disable' : 'Enable'}</Button>
                <Button color="error" onClick={() => removeFolder(folder.id)}>Remove</Button>
              </Stack>
            }>
              <ListItemText primary={folder.path} secondary={folder.enabled ? 'Monitoring enabled' : 'Monitoring disabled'} />
            </ListItem>
          ))}
        </List>
      </Paper>

      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="h6" gutterBottom>Hardware & Transcoder Status</Typography>
        <Stack direction="row" spacing={2} flexWrap="wrap">
          <Chip label={`QSV: ${settings?.qsv_available ? 'Available' : 'Not Available'}`} color={settings?.qsv_available ? 'success' : 'warning'} />
          <Chip label={`Plex: ${settings?.detected_plex_version || 'Not detected'}`} />
          <Chip label={`Software fallback: ${settings?.software_fallback ? 'Enabled' : 'Disabled'}`} />
          <Chip label={`Output bitrate: ${settings?.output_bitrate || 4500} kbps`} />
          <Chip label={`Resolution: ${settings?.output_resolution || '1920x1080'}`} />
        </Stack>
      </Paper>

      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
        <Tabs value={tab} onChange={(_, value) => setTab(value)}>
          <Tab label="Queue" />
          <Tab label="Files" />
          <Tab label="Settings" />
        </Tabs>
      </Box>

      {tab === 0 && (
        <Paper sx={{ p: 2 }}>
          <Stack direction="row" spacing={2} sx={{ mb: 2 }}>
            <Button variant="contained" onClick={pauseQueue}>Pause Queue</Button>
            <Button variant="outlined" onClick={resumeQueue}>Resume Queue</Button>
          </Stack>
          {queue.map((item, index) => (
            <Card key={item.id} sx={{ mb: 1 }}>
              <CardContent>
                <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={2}>
                  <Box>
                    <Typography variant="h6">Queue #{item.id}</Typography>
                    <Typography>State: {item.state}</Typography>
                    <Typography>Progress: {item.progress.toFixed(0)}%</Typography>
                    <Typography>Paused: {item.paused ? 'Yes' : 'No'}</Typography>
                  </Box>
                  <Stack direction="row" spacing={1}>
                    <Button variant="outlined" size="small" onClick={() => moveQueueItem(item.id, 'top')}>Top</Button>
                    <Button variant="outlined" size="small" onClick={() => moveQueueItem(item.id, 'up')} disabled={index === 0}>Up</Button>
                    <Button variant="outlined" size="small" onClick={() => moveQueueItem(item.id, 'down')} disabled={index === queue.length - 1}>Down</Button>
                    <Button variant="contained" color="error" size="small" onClick={() => removeQueueItem(item.id)}>Remove</Button>
                  </Stack>
                </Stack>
              </CardContent>
            </Card>
          ))}
        </Paper>
      )}

      {tab === 1 && (
        <Paper sx={{ p: 2 }}>
          {files.map((file) => (
            <Card key={file.id} sx={{ mb: 1 }}>
              <CardContent>
                <Typography variant="h6">{file.path}</Typography>
                <Typography>HDR: {file.hdr_detected ? 'Yes' : 'No'} ({file.hdr_type || 'Unknown'})</Typography>
                <Typography>Resolution: {file.resolution || 'N/A'}</Typography>
                <Typography>Codec: {file.codec || 'N/A'}</Typography>
                <Typography>Bitrate: {file.bitrate || 'N/A'} kbps</Typography>
                <Typography>Tracks: {file.audio_tracks || 0} audio, {file.subtitle_tracks || 0} subtitles</Typography>
                <Typography>Status: {file.status}</Typography>
              </CardContent>
            </Card>
          ))}
        </Paper>
      )}

      {tab === 2 && settingsForm && (
        <Paper sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>Settings</Typography>
          <Stack spacing={2}>
            <TextField
              label="Max concurrent transcodes"
              type="number"
              value={settingsForm.max_concurrent_transcodes}
              onChange={(e) => setSettingsForm({ ...settingsForm, max_concurrent_transcodes: Number(e.target.value) })}
            />
            <TextField
              label="Output bitrate"
              type="number"
              value={settingsForm.output_bitrate}
              onChange={(e) => setSettingsForm({ ...settingsForm, output_bitrate: Number(e.target.value) })}
            />
            <TextField
              label="Output resolution"
              value={settingsForm.output_resolution}
              onChange={(e) => setSettingsForm({ ...settingsForm, output_resolution: e.target.value })}
            />
            <TextField
              label="Plex transcoder path"
              value={settingsForm.plex_transcoder_path || ''}
              onChange={(e) => setSettingsForm({ ...settingsForm, plex_transcoder_path: e.target.value })}
            />
            <TextField
              label="Scan interval (seconds)"
              type="number"
              value={settingsForm.scan_interval}
              onChange={(e) => setSettingsForm({ ...settingsForm, scan_interval: Number(e.target.value) })}
            />
            <TextField
              label="Log retention (days)"
              type="number"
              value={settingsForm.log_retention_days}
              onChange={(e) => setSettingsForm({ ...settingsForm, log_retention_days: Number(e.target.value) })}
            />
            <Stack direction="row" spacing={2} alignItems="center">
              <Typography>Enable software fallback</Typography>
              <input
                type="checkbox"
                checked={settingsForm.software_fallback}
                onChange={(e) => setSettingsForm({ ...settingsForm, software_fallback: e.target.checked })}
              />
            </Stack>
            <Button variant="contained" onClick={saveSettings}>Save Settings</Button>
          </Stack>
        </Paper>
      )}
    </Container>
  )
}

export default App
