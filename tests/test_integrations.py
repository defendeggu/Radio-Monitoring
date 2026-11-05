"""N1MM+ UDP listener and DX cluster telnet server."""

import socket
import time

import pytest

from radiomoni import rbn
from radiomoni.contest import worked
from radiomoni.integrations import cluster, n1mm

RADIO = b"""<?xml version="1.0" encoding="utf-8"?>
<RadioInfo>
  <app>N1MM</app><StationName>CONTEST-PC</StationName><RadioNr>1</RadioNr>
  <Freq>1402500</Freq><TXFreq>1402500</TXFreq><Mode>CW</Mode><mycall>HB9XX</mycall>
  <IsRunning>True</IsRunning><IsTransmitting>{tx}</IsTransmitting><ActiveRadioNr>1</ActiveRadioNr>
</RadioInfo>"""
CONTACT = b"""<?xml version="1.0" encoding="utf-8"?>
<contactinfo>
  <app>N1MM</app><contestname>CQWWCW</contestname><contestnr>73</contestnr>
  <timestamp>2026-11-28 12:03:38</timestamp><mycall>HB9XX</mycall><band>14</band>
  <rxfreq>1402519</rxfreq><txfreq>1402519</txfreq><operator>HB9XX</operator><mode>CW</mode>
  <call>DL1ABC</call><StationName>CONTEST-PC</StationName><ID>f9ffac4fcd3e479ca86e137df1338531</ID>
</contactinfo>"""
DELETE = b"""<?xml version="1.0" encoding="utf-8"?>
<contactdelete><app>N1MM</app><timestamp>2026-11-28 12:03:38</timestamp><call>DL1ABC</call>
<band>14</band><ID>f9ffac4fcd3e479ca86e137df1338531</ID></contactdelete>"""


def wait_for(cond, timeout: float = 5.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if cond():
            return
        time.sleep(0.02)
    raise AssertionError('condition not met in time')


class TestN1mm:
    def test_parse(self):
        radio = n1mm.parse_packet(RADIO.replace(b'{tx}', b'True'))
        assert radio['type'] == 'radio' and radio['freq_khz'] == 14025.0 and radio['transmitting'] is True
        contact = n1mm.parse_packet(CONTACT)
        assert (contact['call'], contact['band'], contact['mode']) == ('DL1ABC', '20m', 'CW')
        assert n1mm.parse_packet(DELETE)['id'] == 'f9ffac4fcd3e479ca86e137df1338531'
        assert n1mm.parse_packet(b'<other/>') is None
        assert n1mm.parse_packet(b'not xml') is None

    def test_handle(self):
        n1mm.handle(n1mm.parse_packet(CONTACT))
        assert worked.summary()['qsos'] == 1 and worked.all_qsos()[0]['source'] == 'n1mm'
        n1mm.handle(n1mm.parse_packet(CONTACT))               # contactreplace / repeat: same ID, no duplicate
        assert worked.summary()['qsos'] == 1
        n1mm.handle(n1mm.parse_packet(DELETE))
        assert worked.summary()['qsos'] == 0
        n1mm.handle(n1mm.parse_packet(RADIO.replace(b'{tx}', b'True')))
        assert n1mm.is_transmitting()
        n1mm.handle(n1mm.parse_packet(RADIO.replace(b'{tx}', b'False')))
        assert not n1mm.is_transmitting()

    def test_listener_over_udp(self):
        listener = n1mm.N1mmListener(0, host='127.0.0.1')
        listener.start()
        try:
            assert listener.ready.wait(5)
            sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sender.sendto(CONTACT, ('127.0.0.1', listener.bound_port))
            sender.sendto(RADIO.replace(b'{tx}', b'True'), ('127.0.0.1', listener.bound_port))
            wait_for(lambda: worked.summary()['qsos'] == 1 and n1mm.is_transmitting())
            status = n1mm.status()
            assert status['listening'] and status['packets'] == 2 and status['radios'][0]['station'] == 'CONTEST-PC'
        finally:
            listener.stop()

    def test_sender_not_allowed(self):
        listener = n1mm.N1mmListener(0, allowed=['192.0.2.0/24'], host='127.0.0.1')
        listener.start()
        try:
            assert listener.ready.wait(5)
            socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(CONTACT, ('127.0.0.1', listener.bound_port))
            time.sleep(0.5)
            assert worked.summary()['qsos'] == 0
        finally:
            listener.stop()


class TestCluster:
    def test_line_reads_like_rbn(self):
        spot = {'callsign': 'DL1ABC', 'frequency': 14_025_300, 'mode': 'CW', 'snr_db': 18.4, 'wpm': 24.2,
                'type': 'CQ'}
        line = cluster.publish_spot(spot, spotter='HB9XYZ')
        parsed = rbn.parse_spot(line)
        assert parsed['spotter'] == 'HB9XYZ' and parsed['callsign'] == 'DL1ABC' and parsed['khz'] == 14025.3
        assert (parsed['snr_db'], parsed['wpm'], parsed['type']) == (18, 24, 'CQ')
        assert len(line) <= 80

    @pytest.mark.parametrize('extra, tag', [({'new_mults': [{'label': 'x'}]}, 'MULT'), ({'rare': True}, 'RARE'),
                                            ({'priority': 'dupe'}, 'DUPE')])
    def test_comment_tags(self, extra, tag):
        comment = cluster.spot_comment({'callsign': 'P5ABC', 'frequency': 14_025_000, 'type': 'CQ', **extra})
        assert comment.endswith(tag)

    def test_server_sends_spots(self):
        cluster.publish_spot({'callsign': 'OK2PDT', 'frequency': 7_012_000, 'type': 'CQ'}, spotter='HB9XYZ')
        server = cluster.ClusterServer(0, host='127.0.0.1')
        server.start()
        try:
            assert server.ready.wait(5)
            client = socket.create_connection(('127.0.0.1', server.bound_port), timeout=5)
            received = b''

            def read_until(token: bytes) -> None:
                nonlocal received
                while token not in received:
                    received += client.recv(4096)

            read_until(b'login:')
            client.sendall(b'HB9XX\r\n')
            read_until(b'OK2PDT')                        # recent spots right after the login
            wait_for(lambda: len(server.clients) == 1)
            cluster.publish_spot({'callsign': 'F5ABC', 'frequency': 21_030_000, 'type': 'CQ'}, spotter='HB9XYZ')
            read_until(b'F5ABC')
            assert b'Hello HB9XX' in received
            assert cluster.status()['clients'][0]['call'] == 'HB9XX'
            client.sendall(b'bye\r\n')
            wait_for(lambda: not server.clients)
        finally:
            server.stop()
