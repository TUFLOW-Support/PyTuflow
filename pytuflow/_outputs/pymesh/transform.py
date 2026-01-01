import typing

import numpy as np
import pandas as pd

try:
    import shapely
except ImportError:
    from .stubs import shapely


class Transform2D:
    """2D vector transformation class.

    Parameters
    ----------
    translate : list[float], optional
        2x floats (Tx, Ty) that defines the translation transformation. A default value of (0, 0) is used if
        nothing is provided.
    rotate : float, optional
        A float value in degrees counter-clockwise that defines the rotation transformation.
        A default value of 0 is used if nothing is provided.
    scale : list[float, float], optional
        2x floats (Sx, Sy) that defines the scale transformation. A default value of (1, 1) is
        used if nothing is provided.
    pivot :  list[float, float], optional
        2x floats (Ox, Oy) that define the pivot point. The default pivot is (0, 0).
    order: str, optional
        The order of operations. Default = Scale, Rotate, Translate
    proj_transformer : typing.Callable, optional
        A callable function that performs a projection transformation on the points.
    proj_transformer_inverse : typing.Callable, optional
        A callable function that performs the inverse projection transformation on the points.
    """

    def __init__(self, translate: typing.Iterable[float] = (), rotate: float = 0, scale: typing.Iterable[float] = (),
                 pivot: typing.Iterable[float] = (), order: str = 'SRT', proj_transformer: typing.Callable = None,
                 proj_transformer_inverse: typing.Callable = None):
        self.pivot = pivot if pivot else [0., 0.]
        self.translate_param = translate if (isinstance(translate, np.ndarray) and translate.size) or (not isinstance(translate, np.ndarray) and translate) else [0., 0.]
        self.rotate_param = rotate
        self.scale_param = scale if (isinstance(scale, np.ndarray) and scale.size) or (not isinstance(scale, np.ndarray) and scale) else [1., 1.]
        self.proj_transformer = proj_transformer
        self.proj_transformer_inverse = proj_transformer_inverse

        self._was_shapely = False
        self._was_single_point = False
        self.order = order

    def inverse(self) -> 'Transform2D':
        """Returns the inverse transformation.

        Returns
        -------
        Transform2D
            Inverse transformation.
        """
        inv_translate = [-self.translate_param[0], -self.translate_param[1]]
        inv_rotate = -self.rotate_param
        inv_scale = [1. / self.scale_param[0] if self.scale_param[0] != 0 else 0.,
                     1. / self.scale_param[1] if self.scale_param[1] != 0 else 0.]
        return Transform2D(
            translate=inv_translate,
            rotate=inv_rotate,
            scale=inv_scale,
            pivot=self.pivot,
            order=self.order[::-1],
            proj_transformer=self.proj_transformer_inverse,
            proj_transformer_inverse=self.proj_transformer
        )

    def transform(self, points: typing.Iterable[float], order: str = '', dtype = None) -> np.ndarray:
        """Transforms the points.

        Parameters
        ----------
        points : np.ndarray
            Array of 2D vectors.
        order : str, optional
            The order of operations. Default = Scale, Rotate, Translate

        Returns
        -------
        np.ndarray
            Transformed points.
        """
        d = {
            'S': self.scale,
            'R': self.rotate,
            'T': self.translate,
            'P': self.proj_transform
        }
        points = self._save_and_convert_format(points)
        if dtype:
            points = points.astype(dtype)

        used = []
        p = points.copy()
        order = order if order else self.order
        order_list = [x.upper() for x in order]
        while order_list:
            op = order_list.pop(0)
            if op not in d or op in used:
                continue
            used.append(op)
            p = d[op](p)
        return self._restore_format(p)

    def translate(self, points: typing.Iterable[float]) -> np.ndarray:
        """Translates the given points (array of 2D vector) by the ``translate_param``.

        Parameters
        ----------
        points : np.ndarray
            Array of 2D vectors.

        Returns
        -------
        np.ndarray
            Translated points.
        """
        if not isinstance(points, np.ndarray):
            if isinstance(points, (pd.DataFrame, pd.Series)):
                points = points.to_numpy().reshape(-1, 2)
            else:
                points = np.array(points).reshape(-1, 2)
        trans = np.array([
            [1., 0., self.translate_param[0]],
            [0., 1., self.translate_param[1]],
            [0., 0., 1.]
        ])
        points1 = np.array(points)
        if len(points.shape) > 1:
            points1[:,:2] = self._matrix_operation(trans, points[:,:2])
        else:
            points1[:2] = self._matrix_operation(trans, points[:2])
        return points1

    def rotate(self, points: typing.Iterable[float]) -> np.ndarray:
        """Rotates the given points (array of 2D vector) by the ``rotate_param``.

        Parameters
        ----------
        points : np.ndarray
            Array of 2D vectors.

        Returns
        -------
        np.ndarray
            Rotated points.
        """
        if not isinstance(points, np.ndarray):
            if isinstance(points, (pd.DataFrame, pd.Series)):
                points = points.to_numpy().reshape(-1, 2)
            else:
                points = np.array(points).reshape(-1, 2)

        if list(self.pivot) != [0, 0]:
            trans = Transform2D(translate=(-self.pivot[0], -self.pivot[1]), rotate=self.rotate_param)
            points1 = trans.transform(points, order='TR')
            trans.translate_param = self.pivot
            return trans.translate(points1)

        rot = np.array([
            [np.cos(np.radians(self.rotate_param)), -np.sin(np.radians(self.rotate_param))],
            [np.sin(np.radians(self.rotate_param)), np.cos(np.radians(self.rotate_param))]
        ])
        points1 = np.array(points)
        if len(points.shape) > 1:
            points1[:, :2] = self._matrix_operation(rot, points[:, :2])
        else:
            points1[:2] = self._matrix_operation(rot, points[:2])
        return points1

    def scale(self, points: typing.Iterable[float], dtype: str = None) -> np.ndarray:
        """Scales the given points (array of 2D vector) by the ``scale_param``.

        Parameters
        ----------
        points : np.ndarray
            Array of 2D vectors.

        Returns
        -------
        np.ndarray
            Scaled points.
        """
        if not isinstance(points, np.ndarray):
            if isinstance(points, (pd.DataFrame, pd.Series)):
                points = points.to_numpy().reshape(-1, 2)
            else:
                points = pd.DataFrame(np.array(points).reshape(-1, 2))

        if list(self.pivot) != [0, 0]:
            trans = Transform2D(translate=(-self.pivot[0], -self.pivot[1]), scale=self.scale_param)
            points1 = trans.transform(points, order='TS')
            trans.translate_param = self.pivot
            return trans.translate(points1)

        scale = np.array([
            [self.scale_param[0], 0],
            [0, self.scale_param[1]]
        ])
        points1 = np.array(points)
        if len(points.shape) > 1:
            points1[:, :2] = self._matrix_operation(scale, points[:, :2])
        else:
            points1[:2] = self._matrix_operation(scale, points[:2])
        return points1

    def proj_transform(self, points: np.ndarray) -> np.ndarray:
        """Applies the projection transformation to the given points.

        Parameters
        ----------
        points : np.ndarray
            Array of 2D vectors.

        Returns
        -------
        np.ndarray
            Transformed points.
        """
        if not self.proj_transformer:
            return points
        if points.ndim == 1:
            points = points.reshape(-1, 2)
        return self.proj_transformer(points)

    @staticmethod
    def _matrix_operation(trans: np.ndarray, points: np.ndarray) -> pd.DataFrame:
        """Performs matrix operation."""
        p = np.array(points)
        dim = trans.shape[0]
        if dim == 3 and len(p.shape) > 1 and p.shape[1] < 3:
            p = np.append(p, np.ones((p.shape[0], 1)), axis=1)
        elif dim == 3 and len(p.shape) == 1 and p.size < 3:
            p = np.append(p, 1)
        elif dim == 2 and len(p.shape) > 1 and p.shape[1] > 2:
            p = p[:, :2]
        elif dim == 2 and len(p.shape) == 1 and p.size > 2:
            p = p[:2]
        p = np.matvec(trans, p)
        # columns = points.columns[:2].tolist()
        # if dim > 2:
        #     columns.append('z')
        # df = pd.DataFrame(p, columns=columns)
        if len(p.shape) > 1:
            return p[:,:2]
        return p[:2]

    def _save_and_convert_format(self, points: typing.Iterable[float]) -> np.ndarray:
        self._was_shapely = False
        self._was_single_point = False

        if not isinstance(points, np.ndarray):
            if shapely and isinstance(points, shapely.Point):
                self._was_shapely = True
                self._was_single_point = True
                points = np.array([[points.x, points.y]])
            else:
                points = np.array(points).reshape(-1, 2)
        if shapely and isinstance(points[0], shapely.Point):
            self._was_shapely = True
            points = np.array([[p.x, p.y] for p in points]).reshape((-1, 2))

        return points

    def _restore_format(self, points: np.ndarray) -> np.ndarray | shapely.Point:
        if self._was_shapely:
            if self._was_single_point:
                return shapely.Point(points[0, 0], points[0, 1])
            else:
                return np.array([shapely.Point(xy) for xy in points])
        return points
