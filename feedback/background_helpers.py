from html import unescape

from aplus_client.client import AplusApiDict, AplusTokenClient

from .models import (
    Course,
    Student,
)

def get_exercise_questions(exercise_api: AplusApiDict) -> dict[str, dict]:
    # helper method for creating dict of background questionnaire
    questions = {}
    ex_info = exercise_api.get('exercise_info')
    trans_strings = ex_info.get('form_i18n')

    def get_trans_dict(key: str) -> dict[str, str]:
        api_dict = trans_strings.get(key)
        return {k: unescape(api_dict[k]) for k in api_dict.keys()}

    for q in ex_info.get('form_spec'):
        if q.get('type') == 'static':
            continue # skip static texts / instructions
        q_info = {
            k: q.get(k)
            for k in ['required', 'type']
        }
        for k in ['title', 'description']:
            # if api contains fields, add them with translation strings
            k_val = q.get(k)
            if k_val:
                q_info[k] = get_trans_dict(k_val)
        if q.get('type') in ['radio', 'dropdown', 'checkbox']:
            q_answer_opts = {}
            answer_map = q.get('titleMap')
            for k in answer_map.keys():
                q_answer_opts[k] = get_trans_dict(answer_map.get(k))
            q_info['answer_opts'] = q_answer_opts
        questions[q.get('key')] = q_info
    return questions


def get_bg_questionnaires(course: Course, client: AplusTokenClient) -> dict[int, dict[str, dict]]:
    """Key: exercise api id
    Value: dict consisting of
    * url: to exercise api
    * display name
    * questions (dict)
        Key: question key
        Value: dict consisting of
        - required: Boolean
        - type: str ('radio', 'checkbox', 'select', 'textarea')
        If question contains the following:
        - title (dict with language options)
        - description (dict with language options)
        For radio, select and checkboxes, also:
        - answer_opts (dict consisting of key -> language options)
    """
    bg_qs = {}
    # find background questionnaire exercises
    exs_api = client.load_data(f'{course.url}/exercises')
    for mod in exs_api:
        for ex_api in mod.get('exercises'):
            # hack for getting this to work locally
            ex_url = ex_api.get_item('url').replace('localhost', str(course.namespace))
            ex_api = client.load_data(ex_url)
            if 'enrollment' in ex_api.get('status'):
                bg_qs[ex_api.get('id')] = {
                    'url': ex_url,
                    'display_name': ex_api.get('display_name'),
                    'questions': get_exercise_questions(ex_api),
                }
        if len(bg_qs) > 0:
            # assumes all background questionnaires are in the same module
            break
    return bg_qs


def get_student_bg_responses(
        student: Student,
        client: AplusTokenClient,
        bg_qs: dict[int, dict],
        ) -> tuple[int, dict]:
    """Get the student's response to an background questionnaire.
    Returns a tuple with the first value indicating which background questionnaire
    the student had responded to, and the second value the dict of responses.
    The dict has the question keys as keys. For checkboxes, the value is a
    list of the answers. For other question types, the value is the response.
    The dict does not include questions that had no answers.
    """
    for bgq_id, bg_dict in bg_qs.items():
        ex_url = bg_dict['url']
        subs = client.load_data(f'{ex_url}/submissions/{student.api_id}')
        if len(subs) == 0:
            continue
        last_sub = subs[0]
        sub_api = client.load_data(last_sub.get('url'))
        # calc results
        sub_data = sub_api.get('submission_data')
        # create helper dict of submission responses in list per question
        resp_list_dict = {k: [] for k in bg_dict['questions'].keys()}
        for d in sub_data:
            if d[0] in resp_list_dict and d[1] not in ['', '-']: # is question reponse and not empty
                resp_list_dict[d[0]].append(d[1])
        # create final (cleaned up) responses dict
        responses = {}
        for k, resp_list in resp_list_dict.items():
            if len(resp_list) == 0:
                continue # don't add questions with no answers
            if bg_dict['questions'][k]['type'] == 'checkbox':
                responses[k] = resp_list
            else: # should have only one answer
                responses[k] = resp_list[0]
        return (bgq_id, responses)

    # no background questionnaire filled by student
    return (None, None)
