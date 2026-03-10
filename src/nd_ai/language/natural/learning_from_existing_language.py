class LearningFromExistingLanguage:
    """
    The idea is to split the concepts described in a nested key value that already exists in the society or in brain by observer and into small meaning alphabets (hex values) and reconstruct them back inrto words
    """
    def __init__(self, existing_dicts:List[Dict]):
        self._dicts = dicts
        # an embedding based on distribution of values around each other_kind in sequential patterns, similar to paragraphs and texts
        nlp_embedding = self._get_nlp_embedding()
        embeded_keys_vals = []
        for dic in existing_dicts:
            keys = dic.keys()
            vals = dic.values()
            for key, val in zip(keys, vals):
                embedded_key = nlp_embedding.embed(key)
                embedded_val = nlp_embedding.embed(val)
                embeded_key_val = concat(embedded_key, embedded_val)
            embeded_keys_vals.append(embeded_key_val)
        self._get_encoder_decoder().train(embeded_keys_vals)

    def get_alphabets_by_dict(self, nested_dic)->List:
        self._get_encoder().encode(nested_dic)

    def _get_key_val_embedding_alphabets(self, key, val)->List[Sequence]:
        embedded_key = nlp_embedding.embed(key)
        embedded_val = nlp_embedding.embed(val)
        embeded_key_val = concat(embedded_key, embedded_val)
        encodeded_embeded_key_val = self._get_encoder().encode(embeded_key_val)
        alphabets = self._break_embedding_to_alphabets(encodeded_embeded_key_val)
        return encodeded_embeded_key_val

    def get_encoder_decoder(self):
        return

    def get_encoder(self):
        return

    def get_decoder(self):
        return


