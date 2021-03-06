import pandas as pd
import numpy as np
import codecs
import jieba
import jieba.posseg

from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer, TfidfTransformer
from sklearn.linear_model import LogisticRegression
from sklearn import svm
from sklearn.metrics import log_loss
from sklearn import metrics

from joblib import Parallel, delayed
import multiprocessing
import logging
import time


def del_stop_words_train(words, stop_words_set):
    if type(words) != type(" "):
        return np.nan
    result = jieba.posseg.cut(words)
    new_words = []
    for word in result:
        if word.word not in stop_words_set and word.flag is not "x":
            new_words.append(word.word)
    ans = ' '.join(new_words)
    return ans if len(ans) > 0 else np.nan


def del_stop_words_test(words, stop_words_set):
    if type(words) != type(" "):
        return "NaN"
    result = jieba.posseg.cut(words)
    new_words = []
    for word in result:
        if word.word not in stop_words_set and word.flag is not "x":
            new_words.append(word.word)
    ans = ' '.join(new_words)
    return ans if len(ans) > 0 else "NaN"


def log_reg(train, test, metrics_df, cols):
    # Initialize regression
    clf = LogisticRegression(tol=1e-4, solver='saga')
    # optimize the parameters by using saga solver
    # Train the logistic regression
    logger.debug('Training logistic regression for %s', cols)
    clf.fit(train, metrics_df[cols])
    # Predict the test set and train set (to testify)
    logger.debug('Predicting by logistic regression...')
    predicted_train = clf.predict_proba(train_vectorized)[:, 1]
    predicted_test = clf.predict_proba(test)[:, 1]
    logger.info('log loss: %.5f from column %s', log_loss(metrics_df[cols], predicted_train), cols.upper())
    return predicted_test


def svm_reg(train, test, metrics_df, cols):
    # Initialize regression
    svr_rbf = svm.SVR()
    # Train the SVM
    logger.debug('Training SVM regression for %s...', cols)
    svr_rbf.fit(train, metrics_df[cols])
    # Predict the test set and train set (to testify)
    logger.debug('Predicting by SVM regression...')
    predicted_test = svr_rbf.predict(test)
    predicted_train = svr_rbf.predict(train)
    logger.info('log loss: %.5f from column %s', log_loss(metrics_df[cols], predicted_train), cols.upper())
    return predicted_test


if __name__ == '__main__':
    # ----------------Set Path----------------------------------------
    start_time = time.time()
    NUM_CORES = multiprocessing.cpu_count()
    train_path = "./input/training_new.csv"
    test_path = "./input/validation_new.csv"
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)
    # ----------------------------------------------------------------

    raw_train = pd.read_csv(train_path, encoding="utf-8")
    raw_train = raw_train.dropna(subset=["Content"])

    print("Training data shape", raw_train.shape)
    # print(raw_train.describe())
    # ----------------------------------------------------------------

    # ----------------Read Test Data----------------------------------
    test_data = pd.read_csv(test_path, encoding="utf-8")
    test_data = test_data.dropna(subset=["Content"])
    print("Test data shape", test_data.shape)
    # print(test_data.describe())
    # ----------------------------------------------------------------

    # ----------------Remove Stop Words-------------------------------
    stop_words_path = "./input/stop_words_zh.txt"
    stop_list = [line.strip() for line in codecs.open(stop_words_path, 'r', encoding='gb2312').readlines()]
    stop_words = set(stop_list)
    if len(stop_words) > 0:
        logger.info("Got stop words set!\n")

    raw_train["Content"] = Parallel(n_jobs=NUM_CORES, verbose=10)(
        delayed(del_stop_words_train)(raw_train.iloc[index]["Content"], stop_words) for index in range(len(raw_train)))
    raw_train = raw_train.dropna(subset=["Content"])
    print("Training data shape after remove stop words\n", raw_train.shape)

    test_data["Content"] = Parallel(n_jobs=NUM_CORES, verbose=10)(
        delayed(del_stop_words_test)(test_data.iloc[index]["Content"], stop_words) for index in range(len(test_data)))
    test_data = test_data.dropna(subset=["Content"])
    print("Test data shape after remove stop words\n", test_data.shape)

    # ----------------------------------------------------------------

    # ----------------Deal with the dummmy variables------------------
    dummy_fields = ["Label"]

    for each in dummy_fields:
        dummies = pd.get_dummies(raw_train.loc[:, each], prefix=each)
        raw_train = pd.concat([raw_train, dummies], axis=1)

    fields_to_drop = ["Label"]

    data = raw_train.drop(fields_to_drop, axis=1)

    columns = data.columns.tolist()
    metrics = data[columns[1:]]
    # ----------------------------------------------------------------

    # ------------------Vectorization---------------------------------
    all_text = raw_train.append(test_data)
    count_v0 = CountVectorizer()
    counts_all = count_v0.fit_transform(all_text["Content"])
    count_v1 = CountVectorizer(vocabulary=count_v0.vocabulary_)

    counts_train = count_v1.fit_transform(raw_train["Content"])
    print("the shape of train is " + repr(counts_train.shape))

    count_v2 = CountVectorizer(vocabulary=count_v0.vocabulary_)
    counts_test = count_v2.fit_transform(test_data["Content"])
    print("the shape of test is " + repr(counts_test.shape))

    tfidf_transformer = TfidfTransformer()
    train_vectorized = tfidf_transformer.fit(counts_train).transform(counts_train)
    test_vectorized = tfidf_transformer.fit(counts_test).transform(counts_test)

    # # # Initialize vectorizer and apply it to training set
    # # vectorizer = TfidfVectorizer(min_df=3, max_df=0.8,
    # #                              ngram_range=(1, 2),
    # #                              strip_accents='unicode',
    # #                              smooth_idf=True,
    # #                              sublinear_tf=True)
    # #
    # # print('Applying vectorizer to training set...')
    # # vectorizer = vectorizer.fit(data["Content"])
    # # train_vectorized = vectorizer.transform(data["Content"])
    # # print("Train vectorization finished")
    # # # ----------------------------------------------------------------
    # #
    # # test_vectorized = vectorizer.transform(test_data["Content"])

    # ----------------------------------------------------------------

    submission = pd.DataFrame([], columns=columns[1:])

    test_predict = Parallel()

    for col in metrics:
        submission[col] = log_reg(train_vectorized, test_vectorized, metrics, col)

    print("Submission shape\n", submission.shape)
    submission.to_csv("./output/sub_all.csv", index=False)

    end_time = time.time()
    print("Running time: %f s\n" % (end_time - start_time))
