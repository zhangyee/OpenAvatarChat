from dataclasses import Field, dataclass, field
import logging
from torch.multiprocessing import Process, Queue
import torch.multiprocessing as mp

import os
import sys

import librosa
from loguru import logger
import numpy as np
import soundfile as sf
import soxr

from engine_utils.directory_info import DirectoryInfo


spawn_context = mp.get_context('spawn')

class TTSVoxCPMProcessor(spawn_context.Process):
    def __init__(self, handler_root: str, config: any, input_queue: Queue, output_queue: Queue):
        super().__init__()
        self.handler_root = handler_root
        self.model = None
        self.model_name = config.model_name
        self.api_url = config.api_url
        self.ref_audio_path = config.ref_audio_path
        self.ref_audio_text = config.ref_audio_text
        self.sample_rate = config.sample_rate
        self.max_length = getattr(config, 'max_length', 4096)
        self.cfg_value = getattr(config, 'cfg_value', 2.0)
        self.inference_timesteps = getattr(config, 'inference_timesteps', 10)
        self.normalize = getattr(config, 'normalize', True)
        self.denoise = getattr(config, 'denoise', True)
        self.retry_badcase = getattr(config, 'retry_badcase', True)
        self.retry_badcase_max_times = getattr(config, 'retry_badcase_max_times', 3)
        self.retry_badcase_ratio_threshold = getattr(config, 'retry_badcase_ratio_threshold', 6.0)

        self.input_queue = input_queue
        self.output_queue = output_queue
        self.dump_audio = False

    def run(self):
        logger.remove()
        logger.add(sys.stdout, level='INFO')
        if self.dump_audio:
            dump_file_path = os.path.join(DirectoryInfo.get_project_dir(),
                                            "dump_avatar_audio_voxcpm.pcm")
            self.audio_dump_file = open(dump_file_path, "wb")
        logger.info('start voxcpm tts processor')

        # Load VoxCPM model
        if self.api_url is None and self.model_name is not None:
            sys.path.append(os.path.join(self.handler_root, "VoxCPM", "src"))
            try:
                from voxcpm import VoxCPM
                logger.info(f'Loading VoxCPM model from {self.model_name}')
                self.model = VoxCPM.from_pretrained(self.model_name)
                logger.info('VoxCPM model loaded successfully')
            except Exception as e:
                logger.error(f'Failed to load VoxCPM model: {e}')
                raise

            # Test inference with init text
            init_text = '欢迎来到中国2025'
            try:
                test_wav = self.model.generate(
                    text=init_text,
                    prompt_wav_path=self.ref_audio_path,
                    prompt_text=self.ref_audio_text,
                    max_len=self.max_length,
                    cfg_value=self.cfg_value,
                    inference_timesteps=self.inference_timesteps,
                    normalize=self.normalize,
                    denoise=self.denoise,
                    retry_badcase=self.retry_badcase,
                    retry_badcase_max_times=self.retry_badcase_max_times,
                    retry_badcase_ratio_threshold=self.retry_badcase_ratio_threshold,
                )
                # Resample to target sample rate if needed
                if self.sample_rate != 16000:
                    test_wav = librosa.resample(test_wav, orig_sr=16000, target_sr=self.sample_rate)

                test_wav = test_wav[np.newaxis, ...]  # Add channel dimension
                self.output_queue.put({
                    'key': '',
                    'tts_speech': test_wav,
                    'session_id': ''
                })
                logger.debug('voxcpm test completed')
            except Exception as e:
                logger.error(f'VoxCPM test inference failed: {e}')
                return
        elif self.api_url is not None:
            raise TypeError('api_url not supported yet for VoxCPM')

        logger.info('voxcpm tts processor started')
        while True:
            try:
                logger.debug('waiting for voxcpm tts task')
                input_data = self.input_queue.get(timeout=5)
                logger.debug(f'got voxcpm tts task: {input_data}')
            except Exception:
                continue

            input_text = input_data['text']
            key = input_data['key']
            session_id = input_data['session_id']
            use_streaming = input_data.get('streaming', True)

            if len(input_text) < 1:
                logger.info('ignoring empty input_text')
                # Send None to signal completion
                output = {
                    'key': key,
                    'tts_speech': None,
                    'session_id': session_id
                }
                self.output_queue.put(output)
                continue

            try:
                if use_streaming:
                    # Use streaming generation
                    logger.debug(f'streaming generation for text: {input_text}')

                    # Create streaming resampler for this task (if needed)
                    # soxr.ResampleStream maintains internal state to avoid clicks at chunk boundaries
                    stream_resampler = None
                    if self.sample_rate != 16000:
                        stream_resampler = soxr.ResampleStream(
                            16000,              # VoxCPM output sample rate
                            self.sample_rate,   # Target sample rate
                            1,                  # Mono channel
                            dtype='float32'
                        )

                    for chunk in self.model.generate_streaming(
                        text=input_text,
                        prompt_wav_path=self.ref_audio_path,
                        prompt_text=self.ref_audio_text,
                        max_len=self.max_length,
                        cfg_value=self.cfg_value,
                        inference_timesteps=self.inference_timesteps,
                        normalize=self.normalize,
                        denoise=self.denoise,
                        retry_badcase=self.retry_badcase,
                        retry_badcase_max_times=self.retry_badcase_max_times,
                        retry_badcase_ratio_threshold=self.retry_badcase_ratio_threshold,
                    ):
                        if stream_resampler is not None:
                            # Stream resample each chunk immediately (no batching)
                            resampled = stream_resampler.resample_chunk(chunk, last=False)
                            if len(resampled) == 0:
                                continue  # soxr internal buffering, data will come in next chunk

                            resampled = resampled[np.newaxis, ...]  # Add channel dimension

                            if self.dump_audio:
                                self.audio_dump_file.write(resampled.tobytes())

                            output = {
                                'key': key,
                                'tts_speech': resampled,
                                'session_id': session_id
                            }
                            self.output_queue.put(output)
                            logger.debug(f'sent audio chunk: shape={resampled.shape}')
                        else:
                            # No resampling needed, output directly
                            chunk = chunk[np.newaxis, ...]  # Add channel dimension

                            if self.dump_audio:
                                self.audio_dump_file.write(chunk.tobytes())

                            output = {
                                'key': key,
                                'tts_speech': chunk,
                                'session_id': session_id
                            }
                            self.output_queue.put(output)
                            logger.debug(f'sent audio chunk: shape={chunk.shape}')

                    # Flush resampler to get any remaining samples from internal buffer
                    if stream_resampler is not None:
                        final_chunk = stream_resampler.resample_chunk(np.array([], dtype='float32'), last=True)
                        if len(final_chunk) > 0:
                            final_chunk = final_chunk[np.newaxis, ...]
                            if self.dump_audio:
                                self.audio_dump_file.write(final_chunk.tobytes())
                            output = {
                                'key': key,
                                'tts_speech': final_chunk,
                                'session_id': session_id
                            }
                            self.output_queue.put(output)
                            logger.debug(f'sent final resampler flush: shape={final_chunk.shape}')
                else:
                    # Non-streaming generation
                    logger.debug(f'non-streaming generation for text: {input_text}')
                    wav = self.model.generate(
                        text=input_text,
                        prompt_wav_path=self.ref_audio_path,
                        prompt_text=self.ref_audio_text,
                        max_len=self.max_length,
                        cfg_value=self.cfg_value,
                        inference_timesteps=self.inference_timesteps,
                        normalize=self.normalize,
                        denoise=self.denoise,
                        retry_badcase=self.retry_badcase,
                        retry_badcase_max_times=self.retry_badcase_max_times,
                        retry_badcase_ratio_threshold=self.retry_badcase_ratio_threshold,
                    )

                    # Resample if needed
                    if self.sample_rate != 16000:
                        wav = librosa.resample(wav, orig_sr=16000, target_sr=self.sample_rate)

                    wav = wav[np.newaxis, ...]  # Add channel dimension

                    if self.dump_audio:
                        self.audio_dump_file.write(wav.tobytes())

                    output = {
                        'key': key,
                        'tts_speech': wav,
                        'session_id': session_id
                    }
                    self.output_queue.put(output)
                    logger.debug(f'sent audio: shape={wav.shape}')

            except Exception as e:
                logger.error(f'VoxCPM generation failed: {e}')

            # Send None to signal completion
            output = {
                'key': key,
                'tts_speech': None,
                'session_id': session_id
            }
            self.output_queue.put(output)
