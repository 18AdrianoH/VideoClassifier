from token2vec import init_embeddings, some_items

from parser import tokenized_class_titles, tokenized_class_titles_by_char

from token2vec import EMBEDDING_DIM, PAD

from functools import reduce

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim

import random

NUM_EPOCHS = 10
BATCH_SIZE = 1000

LEARNING_RATE = 0.01
TOKENIZATION_TYPE = "char"
EMBEDDING_ALGO = "ngram"
EMBEDDING_TYPES = {
    "char-cbow": 2,
    "char-ngram": 0,
    "paren-cbow": 3,
    "paren-ngram": 1,
}
EMBEDDING_TYPE = EMBEDDING_TYPES["-".join([TOKENIZATION_TYPE, EMBEDDING_ALGO])]


# (filter size, num filters of that size)
FILTERS = [(3, 10), (4, 8), (5, 6)]


class CNN_NLP(nn.Module):
    """
        An 1D Convulational Neural Network for Sentence Classification. based on
        https://chriskhanhtran.github.io/posts/cnn-sentence-classification/
    """

    def __init__(
        self, pretrained_embedding, embed_dim, filters, num_classes, dropout=0.5
    ):

        super(CNN_NLP, self).__init__()

        # Embedding layer
        self.vocab_size, self.embed_dim = pretrained_embedding.shape
        self.embedding = nn.Embedding.from_pretrained(pretrained_embedding)

        # Conv Network
        self.conv1d_list = nn.ModuleList(
            map(
                lambda f: nn.Conv1d(
                    in_channels=self.embed_dim, out_channels=f[1], kernel_size=f[0],
                ),
                filters,
            )
        )

        # Fully-connected layer and Dropout
        self.fc = nn.Linear(reduce(lambda acc, f: acc + f[1], filters, 0), num_classes)
        self.dropout = nn.Dropout(p=dropout)

    def forward(self, inputs):
        # Get embeddings from `inputs`. Output shape: (b, maxlen, embed_dim)
        x_embed = self.embedding(inputs).view((1, -1))

        # Permute `x_embed` to match input shape requirement of `nn.Conv1d`.
        # Output shape: (b, embed_dim, max_len)
        x_reshaped = x_embed.permute(0, 2, 1)

        # Apply CNN and ReLU. Output shape: (b, num_filters[i], L_out)
        x_conv_list = [F.relu(conv1d(x_reshaped)) for conv1d in self.conv1d_list]

        # Max pooling. Output shape: (b, num_filters[i], 1)
        x_pool_list = [
            F.max_pool1d(x_conv, kernel_size=x_conv.shape[2]) for x_conv in x_conv_list
        ]

        # Concatenate x_pool_list to feed the fully connected layer.
        # Output shape: (b, sum(num_filters))
        x_fc = torch.cat([x_pool.squeeze(dim=2) for x_pool in x_pool_list], dim=1)

        # Compute logits. Output shape: (b, n_classes)
        logits = self.fc(self.dropout(x_fc))

        return logits


""" return 
    the embedding (pretrained), 
    the _transform function to get a token and token2ix and return the embedding, 
    and token2ix (mapping tokens to a unique numerical id i.e. index of embedding tensor for embedding vector
"""


def embedding_info(embedding_type=None):
    initialized_embeddings = init_embeddings(as_list=True)
    embedding, _transform, token2ix = initialized_embeddings[
        embedding_type if embedding_type else EMBEDDING_TYPE
    ]
    return embedding, _transform, token2ix


""" return the tokenized titles for the r ight tokenization type and the max length to pad """

# get the tokenized titles by class and max len without padding yet
def tokenized_titles_by_class_and_max_len(tokenization_type=None):
    return (
        tokenized_class_titles(debug=False)
        if tokenization_type == "paren"
        or not tokenization_type
        and TOKENIZATION_TYPE == "paren"
        else tokenized_class_titles_by_char(debug=False)
    )


""" return a copy of the tokenized datastructure but with the titles padded """


def padded_titles(tokenization_type=None):
    tokenized, maxlen = tokenized_titles_by_class_and_max_len(
        tokenization_type=tokenization_type
    )

    return (
        {
            _class: list(
                map(
                    lambda title: title
                    if len(title) == maxlen
                    else title + [PAD] * (maxlen - len(title)),
                    titles,
                )
            )
            for _class, titles in tokenized.items()
        },
        maxlen,
    )


def train():
    # embedding is {tensor (index) -> tensor}
    # _transform is token, token2ix -> tensor(token2ix[token]) (i.e. tensor for index)
    # token2ix is token -> unique # id (the one passed into the tensor in _transform and used by embedding)
    embedding, _transform, token2ix = embedding_info()
    # class : [list of a bunch of padded titles that are tokenized]
    class2titles = padded_titles()
    # class : index in the output tensor corresponding to the
    class2idx = {_class: i for _class, i in enumerate(class2titles.keys())}

    model = CNN_NLP(
        pretrained_embedding=embedding,
        embed_dim=EMBEDDING_DIM,
        filters=FILTERS,
        num_classes=len(class2titles.keys()),
    )

    losses = []
    loss_function = nn.NLLLoss()
    optimizer = optim.SGD(model.parameters(), lr=LEARNING_RATE)

    print(f"training NLP CNN model")
    for epoch in range(epochs):
        print(f"\tepoch {epoch}")

        total_loss = 0
        # this is kind of a gimmick
        # TODO in the future we'll want to do a training validation split
        for target_class, class_titles in class2titles.items():
            for title in some_items(batch_size, class_titles):
                target = torch.zeroes((1, len(class2idx.keys())))
                target[class2idx[target_class]] = 1
                log_target = target  # TODO

                _input = torch.tensor([token2ix[w] for w in title], dtype=torch.long)

                model.zero_grad()
                log_probs = model(_input)

                loss = loss_function(log_probs, log_target)

                loss.backward()
                optimizer.step()

                total_loss += loss.item()
        losses.append(total_loss)

    print(f"Done training.")


if __name__ == "__main__":
    pass
