import argparse
from pathlib import Path
from typing import Optional

from julius4seg import sp_inserter
from julius4seg.sp_inserter import frame_to_second


# If you want to handle error, uncomment-out
# fhandler = FileHandler(logname + '.log')
# fhandler.setLevel(DEBUG)
# sp_inserter.logger.addHandler(fhandler)


def run_segment(
        wav_file: Path,
        input_yomi_file: Path,
        output_seg_file: Path,
        input_yomi_type: str,
        like_openjtalk: bool,
        input_text_file: Optional[Path],
        output_text_file: Optional[Path],
        hmm_model: str,
):
    utt_id = wav_file.name.split('.')[0]

    with input_yomi_file.open() as f:
        base_yomi_text = f.readline().strip()

    if input_yomi_type != 'phoneme':
        conv_funtion = sp_inserter.conv2julius if not like_openjtalk else sp_inserter.conv2openjtalk
        if input_yomi_type == 'katakana':
            base_yomi_text = sp_inserter.kata2hira(base_yomi_text)
        julius_phones = [
            conv_funtion(hira)
            for hira in [sp_inserter.kata2hira(kata) for kata in base_yomi_text.split()]
        ]
    else:
        julius_phones = base_yomi_text.split(' sp ')

    if input_text_file:
        with input_text_file.open() as f:
            base_kan_text = f.readline().strip().split()
    else:
        base_kan_text = ['sym_{}'.format(i) for i in range(len(julius_phones))]

    assert len(base_kan_text) == len(julius_phones)

    dict_1st = sp_inserter.gen_julius_dict_1st(base_kan_text, julius_phones)
    dfa_1st = sp_inserter.gen_julius_dfa(dict_1st.count('\n'))

    with open(f'/tmp/first_pass_{utt_id}.dict', 'w') as f:
        f.write(dict_1st)

    with open(f'/tmp/first_pass_{utt_id}.dfa', 'w') as f:
        f.write(dfa_1st)

    raw_first_output = sp_inserter.julius_sp_insert(str(wav_file), f'/tmp/first_pass_{utt_id}', hmm_model)

    forced_text_with_sp = []
    forced_phones_with_sp = []

    try:
        _, sp_position = sp_inserter.get_sp_inserted_text(raw_first_output, utt_id)

        for j, zipped in enumerate(zip(base_kan_text, julius_phones)):
            forced_text_with_sp.append(zipped[0])
            forced_phones_with_sp.append(zipped[1])
            if j in sp_position:
                forced_text_with_sp.append('<sp>')
                forced_phones_with_sp.append('sp')

        forced_text_with_sp = ' '.join(forced_text_with_sp)
        forced_phones_with_sp = ' '.join(forced_phones_with_sp)
    except:
        pass

    phones_with_sp = sp_inserter.get_sp_inserterd_phone_seqence(raw_first_output, utt_id)

    if len(forced_phones_with_sp) < 2:
        forced_phones_with_sp = phones_with_sp

    dict_2nd = sp_inserter.gen_julius_dict_2nd(forced_phones_with_sp)
    dfa_2nd = sp_inserter.gen_julius_aliment_dfa(dict_2nd.count('\n'))

    with open(f'/tmp/second_pass_{utt_id}.dict', 'w') as f:
        f.write(dict_2nd)

    with open(f'/tmp/second_pass_{utt_id}.dfa', 'w') as f:
        f.write(dfa_2nd)

    raw_second_output = sp_inserter.julius_phone_alignment(str(wav_file), f'/tmp/second_pass_{utt_id}', hmm_model)

    time_alimented_list = sp_inserter.get_time_alimented_list(raw_second_output)
    time_alimented_list = frame_to_second(time_alimented_list)

    if output_text_file:
        with output_text_file.open('w') as f:
            f.write(forced_text_with_sp + '\n')

    with output_seg_file.open('w') as f:
        for ss in time_alimented_list:
            f.write('\t'.join(list(ss)) + '\n')


def main():
    parser = argparse.ArgumentParser('sp insert demo by Julius')

    parser.add_argument('wav_file', type=Path, help='入力音声')
    parser.add_argument('input_yomi_file', type=Path, help='スペース区切りの読みファイル')
    parser.add_argument('output_seg_file', type=Path, help='時間情報付き音素セグメントファイル')

    parser.add_argument('--input_yomi_type', default='katakana', choices=['hiragana', 'katakana', 'phoneme'])
    parser.add_argument('--like_openjtalk', action='store_true', help='OpenJTalkのような音素列にする')

    parser.add_argument('-it', '--input_text_file', type=Path, help='漢字仮名交じり文')
    parser.add_argument('-ot', '--output_text_file', type=Path, help='漢字仮名交じり文にspを挿入したもの')

    parser.add_argument('--hmm_model', help='support mono-phone model only', required=True)

    args = parser.parse_args()

    run_segment(**vars(args))


if __name__ == '__main__':
    main()
