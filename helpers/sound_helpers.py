import asyncio
import os
from typing import Callable, Any, Optional

import discord
from discord import ClientException, VoiceChannel, Guild, AudioSource, VoiceClient
from discord.opus import OpusNotLoaded

from constants import BOT, SONG_PATH
from helpers.youtube_helpers import YTDLSource
from logger import logger
from models.types import GuildSingleton


class SoundTools(GuildSingleton):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._connection: Optional[VoiceClient] = None
        self._dispatcher = None
        self._last_source_path = None

    @property
    def last_source_path(self):
        return self._last_source_path

    async def _close(self):
        if self._connection is None:
            return True
        if self._connection.is_playing() or self._connection.is_paused():
            logger.debug("Stopping current audio")
            self._connection.stop()
        return True

    def _set_guild_voice_client(self, guild: Guild) -> bool:
        self._connection = guild.voice_client
        if self._connection:
            return True
        return False

    async def _connect(self, voice_channel: VoiceChannel):
        """Connect to a VoiceChannel"""
        if not self._connection or not self._connection.is_connected():
            if self._set_guild_voice_client(voice_channel.guild):
                # use an existing VoiceClient in the current guild
                await self._connection.move_to(voice_channel)
            else:
                # create a new VoiceClient
                try:
                    self._connection = await voice_channel.connect()
                except ClientException as err:  # You are already connected to a voice channel.
                    logger.error(f"Error while trying to connect to voice (already connected to voice?): {err}")
                    # todo: understand this possible error
                    return False
                except asyncio.TimeoutError as err:
                    logger.error(f"Timeout error: Could not connect to the voice channel in time: {err}")
                    return False
                except OpusNotLoaded as err:
                    logger.error(f"Library error: The opus library has not been loaded (check requirements?): {err}")
                    return False
        else:
            await self._connection.move_to(voice_channel)
            await asyncio.sleep(1)  # avoid a bug with a delay ?
        return True

    async def _play(self, source: AudioSource, after=None) -> bool:
        """Play an audio source. Returns True on success, False on error."""
        try:
            self._dispatcher = self._connection.play(source, after=after)
        except TypeError as err:
            logger.warning(f"Can not play: Source is not a AudioSource (file error ?): {err}")
            return False
        except ClientException as err:
            logger.error(f"Can not play: Already playing audio or not connected (connection error ?): {err}")
            logger.exception(err)
            return False
        except OpusNotLoaded as err:
            logger.error(f"Can not play: The opus library has not been loaded (check requirements?): {err}")
            return False
        return True

    async def play(self, voice_channel: VoiceChannel, song_path: str, force=False,
                   after: Callable[[Exception], Any] = None) -> bool:
        """Play a song in a VoiceChannel

        :param voice_channel: VoiceChannel where to play the song
        :param song_path: path to an audio file
        :param force: if True, stop the current song if it exists before playing.
        If False, the song is not played if a song is already playing (or paused)
        :param after: the finalizer that is called after the stream is exhausted.
        This function must have a single parameter, error, that denotes an optional
        exception that was raised during playing.
        """
        self._last_source_path = song_path
        if force:
            await self._close()
        if not await self._connect(voice_channel):
            return False
        if self._connection.is_playing() or self._connection.is_paused():
            logger.debug("Cannot play, because a song is already playing or is paused!")
            return False
        if os.path.isfile(os.path.join(SONG_PATH, song_path)):
            song_path = os.path.join(SONG_PATH, song_path)
        if os.path.isfile(song_path):
            source = discord.FFmpegPCMAudio(song_path)
        elif song_path.find("youtu.be") >= 0 or song_path.find("youtube.com") >= 0:
            source = await YTDLSource.from_url(song_path, loop=BOT.loop, stream=True)
        else:
            logger.error(f"Song path is invalid: {song_path}")
            return False
        return await self._play(source, after=after)

    async def stop(self, *_args, **_kwargs):
        return await self._close()

    async def pause(self, *_args, **_kwargs):
        if not self._connection or not self._connection.is_connected():
            return False
        self._connection.pause()
        return True

    async def resume(self, *_args, **_kwargs):
        if not self._connection or not self._connection.is_connected():
            return False
        self._connection.resume()
        return True

    async def disconnect(self, *_args, **_kwargs):
        if self._connection and self._connection.is_connected():
            await self._connection.disconnect()
            return True
        return False

    def is_playing(self):
        return bool(self._connection) and self._connection.is_playing()

    def is_paused(self):
        return bool(self._connection) and self._connection.is_paused()
