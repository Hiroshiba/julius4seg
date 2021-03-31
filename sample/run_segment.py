import argparse
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, List, Optional

from julius4seg import converter, sp_inserter
from julius4seg.sp_inserter import ModelType, frame_to_second, space_symbols


def run_segment(
    wav_file: Path,
    input_yomi_file: Path,
    output_seg_file: Path,
    input_yomi_type: str,
    like_openjtalk: bool,
    only_2nd_path: bool,
    input_text_file: Optional[Path],
    output_text_file: Optional[Path],
    hmm_model: str,
    model_type: ModelType,
    padding_second: float,
    options: Optional[List[str]],
):
    utt_id = wav_file.name.split(".")[0]

    if model_type == ModelType.dnn:
        padding_second += 0.1

    tmp_wav_file: Optional[Any] = None
    if padding_second > 0:
        silence_path = Path(f"/tmp/julius4seg-silence-{padding_second}.wav")
        if not silence_path.exists():
            tmp_silence_path = Path(f"/tmp/julius4seg-silence-tmp-{padding_second}.wav")
            subprocess.run(
                "sox -n -r 16k -c 1 -e signed "
                f"-b 16 {tmp_silence_path} trim 0.0 {padding_second}",
                shell=True,
            )
            tmp_silence_path.rename(silence_path)

        tmp_wav_file = NamedTemporaryFile(suffix=wav_file.suffix, delete=False)
        subprocess.run(
            f"sox {silence_path} {wav_file} {silence_path} {tmp_wav_file.name}",
            shell=True,
        )

        wav_file = Path(tmp_wav_file.name)

    with input_yomi_file.open() as f:
        base_yomi_text = f.readline().strip()

    if input_yomi_type != "phoneme":
        conv_funtion = (
            converter.conv2julius if not like_openjtalk else converter.conv2openjtalk
        )
        if input_yomi_type == "katakana":
            base_yomi_text = sp_inserter.kata2hira(base_yomi_text)
        julius_phones = [conv_funtion(hira) for hira in base_yomi_text.split()]
    else:
        julius_phones = base_yomi_text.split(f" {space_symbols[model_type]} ")

    if model_type == ModelType.dnn:
        julius_phones = [" ".join([f"{p}_I" for p in s.split()]) for s in julius_phones]

    if not only_2nd_path:
        if input_text_file:
            with input_text_file.open() as f:
                base_kan_text = f.readline().strip().split()
        else:
            base_kan_text = ["sym_{}".format(i) for i in range(len(julius_phones))]

        assert len(base_kan_text) == len(julius_phones)

        dict_1st = sp_inserter.gen_julius_dict_1st(
            base_kan_text, julius_phones, model_type
        )
        dfa_1st = sp_inserter.gen_julius_dfa(dict_1st.count("\n"))

        with open(f"/tmp/first_pass_{utt_id}.dict", "w") as f:
            f.write(dict_1st)

        with open(f"/tmp/first_pass_{utt_id}.dfa", "w") as f:
            f.write(dfa_1st)

        raw_first_output = sp_inserter.julius_sp_insert(
            str(wav_file), f"/tmp/first_pass_{utt_id}", hmm_model, model_type, options
        )

        forced_text_list = []
        forced_phones_list = []

        try:
            _, sp_position = sp_inserter.get_sp_inserted_text(raw_first_output)

            for j, (t, p) in enumerate(zip(base_kan_text, julius_phones)):
                forced_text_list.append(t)
                forced_phones_list.append(p)
                if j in sp_position:
                    forced_text_list.append("<sp>")
                    forced_phones_list.append(space_symbols[model_type])

            forced_text_with_sp = " ".join(forced_text_list)
            forced_phones_with_sp = " ".join(forced_phones_list)
        except Exception:
            pass

        phones_with_sp = sp_inserter.get_sp_inserterd_phone_seqence(
            raw_first_output, model_type
        )

        if len(forced_phones_with_sp) < 2:
            forced_phones_with_sp = phones_with_sp

    else:
        forced_phones_with_sp = f" {space_symbols[model_type]} ".join(julius_phones)

    dict_2nd = sp_inserter.gen_julius_dict_2nd(forced_phones_with_sp, model_type)
    dfa_2nd = sp_inserter.gen_julius_aliment_dfa(dict_2nd.count("\n"))

    with open(f"/tmp/second_pass_{utt_id}.dict", "w") as f:
        f.write(dict_2nd)

    with open(f"/tmp/second_pass_{utt_id}.dfa", "w") as f:
        f.write(dfa_2nd)

    raw_second_output = sp_inserter.julius_phone_alignment(
        str(wav_file), f"/tmp/second_pass_{utt_id}", hmm_model, model_type, options
    )

    time_alimented_list = sp_inserter.get_time_alimented_list(raw_second_output)
    time_alimented_list = frame_to_second(time_alimented_list)
    assert len(time_alimented_list) > 0

    if model_type == ModelType.dnn:
        time_alimented_list = [
            (s, e, p.split("_")[0]) for s, e, p in time_alimented_list
        ]
        padding_second -= 0.05

    if padding_second > 0:
        max_second = float(time_alimented_list[-1][1]) - padding_second * 2
        time_alimented_list = [
            (
                str(min(max(0, float(s) - padding_second), max_second)),
                str(min(max(0, float(e) - padding_second), max_second)),
                p,
            )
            for s, e, p in time_alimented_list
        ]

    if output_text_file:
        with output_text_file.open("w") as f:
            f.write(forced_text_with_sp + "\n")

    with output_seg_file.open("w") as f:
        for ss in time_alimented_list:
            f.write("\t".join(list(ss)) + "\n")

    if tmp_wav_file is not None:
        tmp_wav_file.close()


def main():
    parser = argparse.ArgumentParser("sp insert demo by Julius")

    parser.add_argument("wav_file", type=Path, help="入力音声")
    parser.add_argument("input_yomi_file", type=Path, help="スペース区切りの読みファイル")
    parser.add_argument("output_seg_file", type=Path, help="時間情報付き音素セグメントファイル")

    parser.add_argument(
        "--input_yomi_type",
        default="katakana",
        choices=["hiragana", "katakana", "phoneme"],
    )
    parser.add_argument(
        "--like_openjtalk", action="store_true", help="OpenJTalkのような音素列にする"
    )
    parser.add_argument("--only_2nd_path", action="store_true", help="第二パスのみを実行する")

    parser.add_argument("-it", "--input_text_file", type=Path, help="漢字仮名交じり文")
    parser.add_argument(
        "-ot", "--output_text_file", type=Path, help="漢字仮名交じり文にspを挿入したもの"
    )

    parser.add_argument("--hmm_model", required=True)

    parser.add_argument(
        "--model_type",
        choices=[e.value for e in ModelType],
        default=ModelType.gmm,
        type=ModelType,
    )

    parser.add_argument("--padding_second", type=float, default=0)

    parser.add_argument("--options", nargs="*", help="additional julius options")

    args = parser.parse_args()

    run_segment(**vars(args))


if __name__ == "__main__":
    main()
