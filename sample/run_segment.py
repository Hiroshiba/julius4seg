import sys

from julius4seg.sp_inserter import frame_to_second

sys.path.append('..')

from julius4seg import sp_inserter
from pathlib import PurePath, Path
import argparse


# If you want to handle error, uncomment-out
# fhandler = FileHandler(logname + '.log')
# fhandler.setLevel(DEBUG)
# sp_inserter.logger.addHandler(fhandler)


def main(args):
    utt_id = PurePath(args.wav_file).name.split('.')[0]

    with open(args.input_kana_file) as f:
        base_kata_text = f.readline().strip()

    if args.input_text_file:
        with open(args.input_text_file) as f:
            base_kan_text = f.readline().strip().split()
    else:
        base_kan_text = ['sym_{}'.format(i) for i in range(len(base_kata_text.split()))]

    assert len(base_kan_text) == len(base_kata_text.split())

    conv_funtion = sp_inserter.conv2julius if not args.like_openjtalk else sp_inserter.conv2openjtalk
    julius_phones = [conv_funtion(hira) for hira in
                     [sp_inserter.kata2hira(kata) for kata in base_kata_text.split()]]

    dict_1st = sp_inserter.gen_julius_dict_1st(base_kan_text, julius_phones)
    dfa_1st = sp_inserter.gen_julius_dfa(dict_1st.count('\n'))

    with open(f'/tmp/first_pass_{utt_id}.dict', 'w') as f:
        f.write(dict_1st)

    with open(f'/tmp/first_pass_{utt_id}.dfa', 'w') as f:
        f.write(dfa_1st)

    raw_first_output = sp_inserter.julius_sp_insert(args.wav_file, f'/tmp/first_pass_{utt_id}', args.hmm_model)

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
    dfa_2nd = sp_inserter.gen_julius_aliment_dfa()

    with open(f'/tmp/second_pass_{utt_id}.dict', 'w') as f:
        f.write(dict_2nd)

    with open(f'/tmp/second_pass_{utt_id}.dfa', 'w') as f:
        f.write(dfa_2nd)

    raw_second_output = sp_inserter.julius_phone_alignment(args.wav_file, f'/tmp/second_pass_{utt_id}', args.hmm_model)

    time_alimented_list = sp_inserter.get_time_alimented_list(raw_second_output)
    time_alimented_list = frame_to_second(time_alimented_list)

    if args.output_text_file:
        with open(args.output_text_file, 'w') as f:
            f.write(forced_text_with_sp + '\n')

    with open(args.output_seg_file, 'w') as f:
        for ss in time_alimented_list:
            f.write('\t'.join(list(ss)) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser('sp insert demo by Julius')

    parser.add_argument('wav_file', type=Path, help='入力音声')
    parser.add_argument('input_kana_file', type=Path, help='スペース区切りのカナ読みファイル')
    parser.add_argument('output_seg_file', type=Path, help='時間情報付き音素セグメントファイル')

    parser.add_argument('--like_openjtalk', action='store_true', help='OpenJTalkのような音素列にする')

    parser.add_argument('-it', '--input_text_file', help='漢字仮名交じり文')
    parser.add_argument('-ot', '--output_text_file', help='漢字仮名交じり文にspを挿入したもの')

    parser.add_argument('--hmm_model', help='support mono-phone model only')

    args = parser.parse_args()

    main(args)
