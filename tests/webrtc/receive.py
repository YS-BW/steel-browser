"""Receive actual media from the branch's Go signaling endpoint; no custom media bridge."""
import asyncio
import json
import sys
import time

from aiohttp import ClientSession, WSMsgType
from aiortc import RTCConfiguration, RTCPeerConnection, RTCSessionDescription
from aiortc.sdp import candidate_from_sdp


async def main():
    endpoint = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:3001/v1/sessions/webrtc'
    result = {'endpoint': endpoint, 'frames': 0, 'states': [], 'signalMessages': [], 'durationSeconds': 20}
    pc = RTCPeerConnection(RTCConfiguration(iceServers=[]))
    pc.addTransceiver('video', direction='recvonly')
    workers = []

    @pc.on('connectionstatechange')
    async def state_changed():
        result['states'].append(pc.connectionState)

    @pc.on('track')
    def track_received(track):
        result['trackKind'] = track.kind

        async def read_frames():
            try:
                while True:
                    frame = await track.recv()
                    result['frames'] += 1
                    result['width'] = frame.width
                    result['height'] = frame.height
                    if result['frames'] == 1:
                        result['firstFrameAfterSeconds'] = round(time.monotonic() - started, 3)
            except Exception as error:
                result['trackEnded'] = type(error).__name__

        workers.append(asyncio.create_task(read_frames()))

    started = time.monotonic()
    try:
        async with ClientSession() as session:
            async with session.ws_connect(endpoint) as ws:
                await pc.setLocalDescription(await pc.createOffer())
                await ws.send_json({'type': 'offer', 'data': {'type': pc.localDescription.type, 'sdp': pc.localDescription.sdp}})

                async def read_signals():
                    async for message in ws:
                        if message.type != WSMsgType.TEXT:
                            continue
                        payload = json.loads(message.data)
                        kind = payload.get('type')
                        result['signalMessages'].append(kind)
                        if kind == 'answer':
                            data = payload['data']
                            await pc.setRemoteDescription(RTCSessionDescription(sdp=data['sdp'], type=data['type']))
                        elif kind == 'ice-candidate':
                            data = payload['data']
                            candidate = candidate_from_sdp(data['candidate'].removeprefix('candidate:'))
                            candidate.sdpMid = data.get('sdpMid')
                            candidate.sdpMLineIndex = data.get('sdpMLineIndex')
                            await pc.addIceCandidate(candidate)

                workers.append(asyncio.create_task(read_signals()))
                await asyncio.sleep(result['durationSeconds'])
                result['connectionState'] = pc.connectionState
                result['iceConnectionState'] = pc.iceConnectionState
                result['inboundRtp'] = [
                    {'kind': stat.kind, 'packetsReceived': stat.packetsReceived, 'packetsLost': stat.packetsLost}
                    for stat in (await pc.getStats()).values() if stat.type == 'inbound-rtp'
                ]
    except Exception as error:
        result['error'] = f'{type(error).__name__}: {error}'
    finally:
        result['mediaPassed'] = result['frames'] > 5
        for worker in workers:
            worker.cancel()
        await pc.close()
        await asyncio.gather(*workers, return_exceptions=True)
    print(json.dumps(result, ensure_ascii=False, indent=2))


asyncio.run(main())
